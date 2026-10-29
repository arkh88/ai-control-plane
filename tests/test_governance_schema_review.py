"""Day 26: migration drift and disposable-data review."""

from pathlib import Path

import pytest
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine, func, insert, select

from alembic import command
from app.governance_models import (
    ApiCredential,
    Application,
    Base,
    Model,
)

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def migrated_engine(tmp_path):
    """Fresh, migrated, disposable test database."""

    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'review.db'}")

    config = Config(str(ROOT / "alembic.ini"))

    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")

    try:
        yield engine
    finally:
        engine.dispose()


def test_orm_matches_migrations(migrated_engine):
    """Test 1: migrations and ORM describe the same schema."""

    with migrated_engine.connect() as connection:
        differences = compare_metadata(
            MigrationContext.configure(connection),
            Base.metadata,
        )

    assert differences == []


def test_unreviewed_table_is_detected(migrated_engine):
    """Test 2: an unexpected database table creates drift."""

    with migrated_engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE unexpected_table (id INTEGER PRIMARY KEY)"
        )

    with migrated_engine.connect() as connection:
        differences = compare_metadata(
            MigrationContext.configure(connection),
            Base.metadata,
        )

    assert differences != []


def test_sample_data_is_removed_by_rollback(migrated_engine):
    """Test 3: demonstration data need not be retained."""

    with migrated_engine.connect() as connection:
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
                    key_sha256="a" * 64,
                )
            )

            count = connection.scalar(
                select(func.count())
                .select_from(Application)
                .where(Application.application_id == "day26-demo")
            )

            assert count == 1

        finally:
            transaction.rollback()

    with migrated_engine.connect() as connection:
        remaining = connection.scalar(
            select(func.count())
            .select_from(Application)
            .where(Application.application_id == "day26-demo")
        )

    assert remaining == 0
