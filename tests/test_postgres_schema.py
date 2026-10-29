"""Day 26: PostgreSQL-specific migration integration tests."""

import os
from pathlib import Path

import pytest
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import func, insert, inspect, select, text

from alembic import command
from app.governance_db import (
    create_governance_engine,
    database_url_from_env,
)
from app.governance_models import (
    ApiCredential,
    Application,
    Base,
    GovernanceControl,
    GovernancePolicyVersion,
    Model,
    PolicyControlMapping,
)

# The ordinary pytest suite never connects to PostgreSQL.
# This module runs only when explicitly enabled in CI.
if os.getenv("AICP_POSTGRES_TESTS") != "1":
    pytest.skip(
        "PostgreSQL integration tests are separately enabled.",
        allow_module_level=True,
    )


ROOT = Path(__file__).resolve().parents[1]
HEAD = "0003_policy_control_mappings"


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
    }

    with postgres_engine.connect() as connection:
        revision = connection.scalar(
            text("SELECT version_num FROM alembic_version")
        )

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
