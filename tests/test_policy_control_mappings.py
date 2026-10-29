"""Day 27: versioned governance control mapping tests."""

from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, delete, event, func, inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from alembic import command
from app.governance_controls import CONTROL_BY_REASON, CONTROL_CATALOG
from app.governance_models import (
    GovernanceControl,
    GovernancePolicyVersion,
    PolicyControlMapping,
)

ROOT = Path(__file__).resolve().parents[1]
POLICY_VERSION = "model-access/v1"

OPA_REASONS = (
    "ALLOW",
    "MODEL_NOT_ALLOWED",
    "UNKNOWN_APPLICATION",
    "MODEL_NOT_REGISTERED",
)


@pytest.fixture
def database(tmp_path):
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'day27.db'}")

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    config = Config(str(ROOT / "alembic.ini"))

    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")

    try:
        yield engine
    finally:
        engine.dispose()


def seed_catalog(engine):
    """Insert internal catalog data into a disposable test DB."""

    with Session(engine) as session:
        session.add_all(
            GovernanceControl(
                control_id=control_id,
                objective=objective,
            )
            for control_id, objective in CONTROL_CATALOG.items()
        )

        session.add(
            GovernancePolicyVersion(
                policy_version=POLICY_VERSION,
                policy_ref="aicp.authz.decision",
                description="Model access authorization",
            )
        )
        session.commit()


# Test 1: the database contains the intended relationships.
def test_mapping_schema_has_two_foreign_keys(database):
    inspector = inspect(database)

    assert {
        "controls",
        "policy_versions",
        "policy_control_mappings",
    }.issubset(set(inspector.get_table_names()))

    foreign_keys = inspector.get_foreign_keys("policy_control_mappings")

    assert {fk["referred_table"] for fk in foreign_keys} == {
        "controls",
        "policy_versions",
    }

    pk = inspector.get_pk_constraint("policy_control_mappings")

    assert set(pk["constrained_columns"]) == {
        "policy_version",
        "decision_reason",
        "control_id",
    }


# Test 2: all existing OPA reasons map to their internal controls.
def test_opa_reason_mappings_match_python_catalog(database):
    seed_catalog(database)

    with Session(database) as session:
        for reason in OPA_REASONS:
            for control_id in CONTROL_BY_REASON[reason]:
                session.add(
                    PolicyControlMapping(
                        policy_version=POLICY_VERSION,
                        decision_reason=reason,
                        control_id=control_id,
                    )
                )

        session.commit()

        actual = set(
            session.execute(
                select(
                    PolicyControlMapping.decision_reason,
                    PolicyControlMapping.control_id,
                )
            ).all()
        )

    expected = {
        (reason, control_id)
        for reason in OPA_REASONS
        for control_id in CONTROL_BY_REASON[reason]
    }

    assert actual == expected


# Tests 3 and 4: invalid foreign-key references fail.
@pytest.mark.parametrize(
    ("version", "control_id"),
    [
        (POLICY_VERSION, "AICP-NOT-REGISTERED"),
        ("nonexistent-policy/v9", "AICP-AC-001"),
    ],
)
def test_unregistered_mapping_reference_is_rejected(database, version, control_id):
    seed_catalog(database)

    with pytest.raises(IntegrityError):
        with Session(database) as session:
            session.add(
                PolicyControlMapping(
                    policy_version=version,
                    decision_reason="ALLOW",
                    control_id=control_id,
                )
            )
            session.commit()


# Test 5: duplicate mappings cannot be inserted.
def test_duplicate_mapping_is_rejected(database):
    seed_catalog(database)

    mapping = {
        "policy_version": POLICY_VERSION,
        "decision_reason": "ALLOW",
        "control_id": "AICP-AC-001",
    }

    with Session(database) as session:
        session.add(PolicyControlMapping(**mapping))
        session.commit()

    with pytest.raises(IntegrityError):
        with Session(database) as session:
            session.add(PolicyControlMapping(**mapping))
            session.commit()


# Test 6: a new version has its own independent mapping.
def test_mapping_is_scoped_to_policy_version(database):
    seed_catalog(database)

    with Session(database) as session:
        session.add(
            GovernancePolicyVersion(
                policy_version="model-access/v2",
                policy_ref="aicp.authz.decision",
                description="Test-only second version",
            )
        )

        session.add_all(
            [
                PolicyControlMapping(
                    policy_version=version,
                    decision_reason="ALLOW",
                    control_id="AICP-AC-001",
                )
                for version in (
                    POLICY_VERSION,
                    "model-access/v2",
                )
            ]
        )

        session.commit()

        count = session.scalar(select(func.count()).select_from(PolicyControlMapping))

        assert count == 2


# Test 7: a referenced policy version cannot be deleted.
def test_policy_version_delete_is_restricted(database):
    seed_catalog(database)

    with Session(database) as session:
        session.add(
            PolicyControlMapping(
                policy_version=POLICY_VERSION,
                decision_reason="ALLOW",
                control_id="AICP-AC-001",
            )
        )
        session.commit()

    with pytest.raises(IntegrityError):
        with database.begin() as connection:
            connection.execute(
                delete(GovernancePolicyVersion).where(
                    GovernancePolicyVersion.policy_version == POLICY_VERSION
                )
            )
