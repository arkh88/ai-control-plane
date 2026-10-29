"""Relational integrity tests for Day 25 governance tables."""

import hashlib
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, event, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from alembic import command
from app.governance_models import ApiCredential, Application, Model

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def migrated_db(tmp_path):
    """Apply migrations to a disposable SQLite database."""

    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'governance.db'}")

    @event.listens_for(engine, "connect")
    def enforce_foreign_keys(dbapi_connection, connection_record):
        # SQLite requires foreign keys to be enabled explicitly.
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


def seed_application(engine):
    with Session(engine) as session:
        session.add(
            Application(
                application_id="demo-app",
                display_name="Demo Application",
            )
        )
        session.commit()


# Test 1: schema and relationships exist.
def test_core_tables_and_foreign_key_exist(migrated_db):
    inspector = inspect(migrated_db)

    assert set(inspector.get_table_names()) == {
        "alembic_version",
        "applications",
        "api_credentials",
        "models",
        "controls",
        "policy_versions",
        "policy_control_mappings",
    }

    columns = {column["name"] for column in inspector.get_columns("api_credentials")}

    assert "key_sha256" in columns
    assert "api_key" not in columns

    foreign_keys = inspector.get_foreign_keys("api_credentials")

    assert len(foreign_keys) == 1
    assert foreign_keys[0]["referred_table"] == "applications"


# Test 2: valid application/credential relationship.
def test_valid_application_credential_relationship(migrated_db):
    digest = hashlib.sha256(b"test-value-not-a-live-key").hexdigest()

    with Session(migrated_db) as session:
        application = Application(
            application_id="demo-app",
            display_name="Demo Application",
        )

        session.add(
            ApiCredential(
                credential_id="cred-1",
                application=application,
                key_sha256=digest,
            )
        )
        session.commit()

        credential = session.get(
            ApiCredential,
            "cred-1",
        )

        assert credential.application.application_id == ("demo-app")
        assert credential.key_sha256 == digest
        assert credential.is_active is True


# Tests 3 and 4: application/model IDs must be unique.
@pytest.mark.parametrize(
    "kind",
    ["application", "model"],
)
def test_duplicate_identifier_is_rejected(migrated_db, kind):
    entity_type = Application if kind == "application" else Model

    values = (
        {
            "application_id": "demo-app",
            "display_name": "Demo",
        }
        if kind == "application"
        else {
            "model_id": "local-small",
            "provider_id": "mock-provider",
        }
    )

    with Session(migrated_db) as session:
        session.add(entity_type(**values))
        session.commit()

    with pytest.raises(IntegrityError):
        with Session(migrated_db) as session:
            session.add(entity_type(**values))
            session.commit()


# Test 5: credential digests must be unique.
def test_duplicate_digest_is_rejected(migrated_db):
    seed_application(migrated_db)

    digest = "a" * 64

    with Session(migrated_db) as session:
        session.add(
            ApiCredential(
                credential_id="cred-1",
                application_id="demo-app",
                key_sha256=digest,
            )
        )
        session.commit()

    with pytest.raises(IntegrityError):
        with Session(migrated_db) as session:
            session.add(
                ApiCredential(
                    credential_id="cred-2",
                    application_id="demo-app",
                    key_sha256=digest,
                )
            )
            session.commit()


# Test 6: credentials cannot reference missing applications.
def test_orphan_credential_is_rejected(migrated_db):
    with pytest.raises(IntegrityError):
        with Session(migrated_db) as session:
            session.add(
                ApiCredential(
                    credential_id="orphan",
                    application_id="not-registered",
                    key_sha256="b" * 64,
                )
            )
            session.commit()


# Test 7: invalid digest length is rejected.
def test_bad_digest_length_is_rejected(migrated_db):
    seed_application(migrated_db)

    with pytest.raises(IntegrityError):
        with Session(migrated_db) as session:
            session.add(
                ApiCredential(
                    credential_id="invalid",
                    application_id="demo-app",
                    key_sha256="short",
                )
            )
            session.commit()
