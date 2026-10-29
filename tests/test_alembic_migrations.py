"""Tests for the Day 24 Alembic baseline."""

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text

from alembic import command

ROOT = Path(__file__).resolve().parents[1]
BASELINE = "0001_governance_baseline"
HEAD = "0002_core_governance_tables"


def migration_config(connection=None):
    config = Config(str(ROOT / "alembic.ini"))

    if connection is not None:
        config.attributes["connection"] = connection

    return config


def test_baseline_is_current_migration_head():
    """Test 1: the initial revision exists."""

    scripts = ScriptDirectory.from_config(migration_config())

    assert scripts.get_current_head() == HEAD
    assert scripts.get_revision(HEAD).down_revision == BASELINE


def test_fresh_database_can_upgrade(tmp_path):
    """Test 2: a new database receives version tracking."""

    path = tmp_path / "fresh.db"
    engine = create_engine(f"sqlite+pysqlite:///{path}")

    try:
        with engine.begin() as connection:
            command.upgrade(
                migration_config(connection),
                "head",
            )

        assert set(inspect(engine).get_table_names()) == {
            "alembic_version",
            "applications",
            "api_credentials",
            "models",
        }

        with engine.connect() as connection:
            version = connection.scalar(text("SELECT version_num FROM alembic_version"))

        assert version == HEAD

    finally:
        engine.dispose()


def test_repeated_upgrade_preserves_existing_data(tmp_path):
    """Test 3: a second upgrade is non-destructive."""

    path = tmp_path / "repeat.db"
    engine = create_engine(f"sqlite+pysqlite:///{path}")

    try:
        with engine.begin() as connection:
            connection.execute(text("CREATE TABLE keep_me (id INTEGER PRIMARY KEY)"))
            connection.execute(text("INSERT INTO keep_me (id) VALUES (7)"))

            command.upgrade(
                migration_config(connection),
                "head",
            )

        # Apply the exact same migration again.
        with engine.begin() as connection:
            command.upgrade(
                migration_config(connection),
                "head",
            )

        with engine.connect() as connection:
            saved_id = connection.scalar(text("SELECT id FROM keep_me"))
            revision = connection.scalar(
                text("SELECT version_num FROM alembic_version")
            )

        assert saved_id == 7
        assert revision == HEAD

    finally:
        engine.dispose()


def test_disposable_database_can_downgrade_and_upgrade(
    tmp_path,
):
    """Test 4: the empty baseline is reversible."""

    path = tmp_path / "reversible.db"
    engine = create_engine(f"sqlite+pysqlite:///{path}")

    try:
        with engine.begin() as connection:
            command.upgrade(
                migration_config(connection),
                "head",
            )

        with engine.begin() as connection:
            command.downgrade(
                migration_config(connection),
                "base",
            )

        with engine.connect() as connection:
            remaining = connection.scalar(text("SELECT COUNT(*) FROM alembic_version"))

        assert remaining == 0

        with engine.begin() as connection:
            command.upgrade(
                migration_config(connection),
                "head",
            )

        with engine.connect() as connection:
            revision = connection.scalar(
                text("SELECT version_num FROM alembic_version")
            )

        assert revision == HEAD

    finally:
        engine.dispose()
