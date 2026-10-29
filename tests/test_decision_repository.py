"""Day 28: transactional decision repository tests."""

from pathlib import Path
from uuid import uuid4

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from alembic import command
from app.decision_repository import (
    DecisionRepositoryError,
    PostgresDecisionRepository,
)
from app.evidence import EvidenceRecord

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def database(tmp_path):
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'decisions.db'}")
    config = Config(str(ROOT / "alembic.ini"))

    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")

    try:
        yield engine
    finally:
        engine.dispose()


def make_record(**changes):
    data = {
        "request_id": str(uuid4()),
        "application_id": "test-app",
        "model_id": "local-small",
        "outcome": "allow",
        "reason": "ALLOW",
        "policy_version": "model-access/v1",
    }
    data.update(changes)
    return EvidenceRecord(**data)


# Test 1: schema exists and excludes sensitive request fields.
def test_decisions_schema_is_minimal(database):
    columns = {col["name"] for col in inspect(database).get_columns("decisions")}

    assert {
        "evidence_id",
        "request_id",
        "occurred_at",
        "application_id",
        "model_id",
        "outcome",
        "reason",
        "policy_ref",
        "policy_version",
        "control_ids",
    } == columns

    repo = PostgresDecisionRepository(database)

    assert repo.get_by_request_id(str(uuid4())) is None


# Test 2: a successful write is visible from a new connection.
def test_approved_decision_is_committed(database):
    repo = PostgresDecisionRepository(database)
    record = make_record()

    repo.write(record)

    saved = repo.get_by_request_id(record.request_id)

    assert saved is not None
    assert saved.evidence_id == record.evidence_id
    assert saved.request_id == record.request_id
    assert saved.outcome == "allow"
    assert saved.reason == "ALLOW"
    assert saved.policy_version == "model-access/v1"
    assert saved.control_ids == (
        "AICP-AC-001",
        "AICP-EV-001",
    )


# Test 3: duplicate request IDs cannot overwrite evidence.
def test_duplicate_request_id_is_rejected(database):
    repo = PostgresDecisionRepository(database)

    first = make_record()
    duplicate = make_record(
        request_id=first.request_id,
        outcome="deny",
        reason="MODEL_NOT_ALLOWED",
    )

    repo.write(first)

    with pytest.raises(DecisionRepositoryError):
        repo.write(duplicate)

    saved = repo.get_by_request_id(first.request_id)

    assert saved is not None
    assert saved.evidence_id == first.evidence_id
    assert saved.outcome == "allow"


# Test 4: unknown models must still have denial evidence.
def test_unknown_model_denial_can_be_stored(database):
    repo = PostgresDecisionRepository(database)
    record = make_record(
        model_id="unregistered-model",
        outcome="deny",
        reason="MODEL_NOT_REGISTERED",
    )

    repo.write(record)
    saved = repo.get_by_request_id(record.request_id)

    assert saved is not None
    assert saved.model_id == "unregistered-model"
    assert saved.outcome == "deny"
    assert "AICP-RT-001" in saved.control_ids


# Test 5: OPA errors preserve missing version information.
def test_opa_error_keeps_not_reported_version(database):
    repo = PostgresDecisionRepository(database)
    record = make_record(
        outcome="error",
        reason="POLICY_EVALUATION_ERROR",
        policy_version="not_reported",
    )

    repo.write(record)
    saved = repo.get_by_request_id(record.request_id)

    assert saved is not None
    assert saved.outcome == "error"
    assert saved.policy_version == "not_reported"
    assert saved.control_ids == (
        "AICP-FC-001",
        "AICP-EV-001",
    )


# Test 6: the database rejects unsupported outcome values.
def test_invalid_outcome_is_rejected(database):
    repo = PostgresDecisionRepository(database)
    record = make_record(outcome="unsupported")

    with pytest.raises(DecisionRepositoryError):
        repo.write(record)

    assert repo.get_by_request_id(record.request_id) is None


# Test 7: unknown governance reasons fail rather than vanish.
def test_unmapped_reason_is_rejected(database):
    repo = PostgresDecisionRepository(database)
    record = make_record(reason="UNKNOWN_CONTROL_REASON")

    with pytest.raises(DecisionRepositoryError):
        repo.write(record)

    assert repo.get_by_request_id(record.request_id) is None


# Test 8: storage failures are surfaced to the caller.
def test_missing_decision_table_raises_repository_error():
    # Deliberately omit migrations to simulate unusable storage.
    engine = create_engine("sqlite+pysqlite:///:memory:")

    try:
        repo = PostgresDecisionRepository(engine)

        with pytest.raises(DecisionRepositoryError):
            repo.write(make_record())
    finally:
        engine.dispose()
