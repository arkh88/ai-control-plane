"""Day 26: PostgreSQL-specific migration integration tests."""

import asyncio
import os
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, insert, inspect, select, text

from alembic import command
from app.async_decision_repository import AsyncDecisionRepository
from app.decision_repository import PostgresDecisionRepository
from app.evidence import EvidenceRecord, get_evidence_store
from app.governance_db import (
    create_async_governance_engine,
    create_governance_engine,
    database_url_from_env,
)
from app.governance_models import (
    ApiCredential,
    Application,
    Base,
    GovernanceControl,
    GovernanceDecision,
    GovernancePolicyVersion,
    Model,
    PolicyControlMapping,
)
from app.main import app
from app.provider_client import get_provider_client

# The ordinary pytest suite never connects to PostgreSQL.
# This module runs only when explicitly enabled in CI.
if os.getenv("AICP_POSTGRES_TESTS") != "1":
    pytest.skip(
        "PostgreSQL integration tests are separately enabled.",
        allow_module_level=True,
    )


ROOT = Path(__file__).resolve().parents[1]
HEAD = "0004_governance_decisions"


@pytest.fixture(scope="module")
def postgres_engine():
    """Connect only to the dedicated disposable CI database."""

    url = database_url_from_env()

    if url.database != "aicp_ci" or url.host not in {"127.0.0.1", "localhost"}:
        pytest.fail(
            "PostgreSQL tests require the isolated aicp_ci "
            "database on the local CI runner."
        )

    engine = create_governance_engine(url)

    try:
        config = Config(str(ROOT / "alembic.ini"))

        with engine.begin() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, "head")

        yield engine

    finally:
        engine.dispose()


def test_postgres_migration_applies(postgres_engine):
    """Test 1: verify real PostgreSQL tables and revision."""

    tables = set(inspect(postgres_engine).get_table_names())

    assert tables == {
        "alembic_version",
        "applications",
        "api_credentials",
        "models",
        "controls",
        "policy_versions",
        "policy_control_mappings",
        "decisions",
    }

    with postgres_engine.connect() as connection:
        revision = connection.scalar(text("SELECT version_num FROM alembic_version"))

    assert revision == HEAD


def test_postgres_upgrade_is_repeatable(postgres_engine):
    """Test 2: rerunning the upgrade makes no schema changes."""

    config = Config(str(ROOT / "alembic.ini"))

    with postgres_engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")

    with postgres_engine.connect() as connection:
        revision = connection.scalar(text("SELECT version_num FROM alembic_version"))

    assert revision == HEAD


def test_postgres_schema_matches_orm(postgres_engine):
    """Test 3: check for unexpected PostgreSQL schema drift."""

    with postgres_engine.connect() as connection:
        differences = compare_metadata(
            MigrationContext.configure(connection),
            Base.metadata,
        )

    assert differences == []


def test_postgres_demo_data_rolls_back(postgres_engine):
    """Test 4: verify example records are not retained."""

    with postgres_engine.connect() as connection:
        transaction = connection.begin()

        try:
            connection.execute(
                insert(Application).values(
                    application_id="day26-demo",
                    display_name="Temporary Demo",
                )
            )

            connection.execute(
                insert(Model).values(
                    model_id="day26-model",
                    provider_id="mock-provider",
                )
            )

            connection.execute(
                insert(ApiCredential).values(
                    credential_id="day26-credential",
                    application_id="day26-demo",
                    key_sha256="b" * 64,
                )
            )

            assert (
                connection.scalar(
                    select(func.count())
                    .select_from(Application)
                    .where(Application.application_id == "day26-demo")
                )
                == 1
            )

        finally:
            transaction.rollback()

    with postgres_engine.connect() as connection:
        assert (
            connection.scalar(
                select(func.count())
                .select_from(Application)
                .where(Application.application_id == "day26-demo")
            )
            == 0
        )


def test_postgres_policy_control_mapping_round_trip(
    postgres_engine,
):
    """Test 5: PostgreSQL accepts a valid relational mapping."""

    with postgres_engine.connect() as connection:
        transaction = connection.begin()

        try:
            connection.execute(
                insert(GovernanceControl).values(
                    control_id="AICP-AC-001",
                    objective="Application authorization",
                )
            )

            connection.execute(
                insert(GovernancePolicyVersion).values(
                    policy_version="model-access/v1",
                    policy_ref="aicp.authz.decision",
                    description="Model access policy",
                )
            )

            connection.execute(
                insert(PolicyControlMapping).values(
                    policy_version="model-access/v1",
                    decision_reason="ALLOW",
                    control_id="AICP-AC-001",
                )
            )

            result = connection.execute(
                select(
                    PolicyControlMapping.decision_reason,
                    PolicyControlMapping.control_id,
                )
            ).one()

            assert result.decision_reason == "ALLOW"
            assert result.control_id == "AICP-AC-001"

        finally:
            # No catalog test data remains in PostgreSQL.
            transaction.rollback()


def test_postgres_decision_commit_and_readback(
    postgres_engine,
):
    """Test 6: a decision is committed and visible in PostgreSQL."""

    repository = PostgresDecisionRepository(postgres_engine)

    record = EvidenceRecord(
        request_id=str(uuid4()),
        application_id="test-app",
        model_id="unknown-model",
        outcome="deny",
        reason="MODEL_NOT_REGISTERED",
        policy_version="model-access/v1",
    )

    try:
        repository.write(record)

        # This lookup opens a separate database connection.
        saved = repository.get_by_request_id(record.request_id)

        assert saved is not None
        assert saved.evidence_id == record.evidence_id
        assert saved.request_id == record.request_id
        assert saved.outcome == "deny"
        assert saved.reason == "MODEL_NOT_REGISTERED"
        assert "AICP-RT-001" in saved.control_ids

    finally:
        # The dedicated CI database retains no test decision.
        with postgres_engine.begin() as connection:
            connection.execute(
                delete(GovernanceDecision).where(
                    GovernanceDecision.request_id == record.request_id
                )
            )


def test_async_postgres_decision_round_trip(postgres_engine):
    """Test 7: native async PostgreSQL commit and readback."""

    record = EvidenceRecord(
        request_id=str(uuid4()),
        application_id="test-app",
        model_id="local-small",
        outcome="allow",
        reason="ALLOW",
        policy_version="model-access/v1",
    )

    async def scenario():
        engine = create_async_governance_engine(database_url_from_env())
        repository = AsyncDecisionRepository(engine)

        try:
            await repository.write(record)

            saved = await repository.get_by_request_id(record.request_id)

            assert saved is not None
            assert saved.evidence_id == record.evidence_id
            assert saved.outcome == "allow"
            assert saved.control_ids == (
                "AICP-AC-001",
                "AICP-EV-001",
            )

        finally:
            try:
                async with engine.begin() as connection:
                    await connection.execute(
                        delete(GovernanceDecision).where(
                            GovernanceDecision.request_id == record.request_id
                        )
                    )
            finally:
                await engine.dispose()

    asyncio.run(scenario())


def test_async_gateway_commits_before_provider(
    postgres_engine,
    monkeypatch,
):
    """Test 8: provider sees committed PostgreSQL evidence."""

    provider_calls = []
    provider_app = FastAPI()
    saved_request_id = None

    @provider_app.post("/v1/chat/completions")
    async def mocked_provider():
        engine = app.state.governance_async_engine

        # This uses a separate PostgreSQL connection.
        async with engine.connect() as connection:
            result = await connection.execute(
                select(GovernanceDecision.request_id).where(
                    GovernanceDecision.application_id == "test-app",
                    GovernanceDecision.model_id == "local-small",
                    GovernanceDecision.outcome == "allow",
                )
            )
            request_ids = result.scalars().all()

        assert len(request_ids) == 1
        provider_calls.append(request_ids[0])

        # The upstream provider is called only after evidence
        # is readable from a separate connection.
        return {
            "id": "chatcmpl-async-postgres",
            "object": "chat.completion",
            "created": 1700000000,
            "model": "local-small",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "Approved",
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": None,
        }

    async def override_provider():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=provider_app),
            base_url="http://mock-provider:8001",
            trust_env=False,
        ) as provider:
            yield provider

    # Use actual backend selection instead of the
    # shared fixture's SQLite evidence override.
    monkeypatch.delitem(
        app.dependency_overrides,
        get_evidence_store,
        raising=False,
    )

    monkeypatch.setitem(
        app.dependency_overrides,
        get_provider_client,
        override_provider,
    )

    monkeypatch.setenv(
        "AICP_EVIDENCE_BACKEND",
        "postgres",
    )

    try:
        # The context manager starts the FastAPI lifespan.
        with TestClient(app) as gateway:
            response = gateway.post(
                "/v1/chat/completions",
                json={
                    "model": "local-small",
                    "messages": [
                        {
                            "role": "user",
                            "content": "Async PostgreSQL test",
                        }
                    ],
                    "stream": False,
                },
            )

            saved_request_id = response.headers.get("X-Request-ID")

            assert response.status_code == 200
            assert saved_request_id is not None
            assert provider_calls == [saved_request_id]

        # Verify persistence using the separate
        # synchronous CI engine.
        with postgres_engine.connect() as connection:
            row = (
                connection.execute(
                    select(GovernanceDecision.__table__).where(
                        GovernanceDecision.request_id == saved_request_id
                    )
                )
                .mappings()
                .one()
            )

        assert row["outcome"] == "allow"
        assert row["reason"] == "ALLOW"

    finally:
        if saved_request_id is not None:
            with postgres_engine.begin() as connection:
                connection.execute(
                    delete(GovernanceDecision).where(
                        GovernanceDecision.request_id == saved_request_id
                    )
                )
