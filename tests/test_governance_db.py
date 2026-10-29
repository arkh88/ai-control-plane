"""Tests for the new governance database connection layer."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import URL

from app.governance_db import (
    REQUIRED_SETTINGS,
    check_database_connection,
    create_governance_engine,
    database_url_from_env,
)


# 1. Fail explicitly when configuration is missing.
def test_missing_database_configuration(monkeypatch):
    for setting in REQUIRED_SETTINGS:
        monkeypatch.delenv(setting, raising=False)

    with pytest.raises(
        RuntimeError,
        match="Missing governance database configuration",
    ):
        database_url_from_env()


# 2. Build the URL correctly without exposing the password.
def test_database_url_configuration(monkeypatch):
    settings = {
        "AICP_GOVERNANCE_DB_HOST": "postgres",
        "AICP_GOVERNANCE_DB_USER": "aicp",
        "AICP_GOVERNANCE_DB_PASSWORD": "test@secret/password",
        "AICP_GOVERNANCE_DB_NAME": "aicp",
    }

    for key, value in settings.items():
        monkeypatch.setenv(key, value)

    url = database_url_from_env()

    assert url.drivername == "postgresql+psycopg"
    assert url.host == "postgres"
    assert url.username == "aicp"
    assert url.database == "aicp"
    assert url.password == "test@secret/password"

    # SQLAlchemy's default URL string representation
    # must not disclose the credential.
    assert "test@secret/password" not in str(url)


# 3. Creating an engine does not require a running database.
def test_engine_creation_is_lazy():
    url = URL.create(
        "postgresql+psycopg",
        username="aicp",
        password="test-password",
        host="unreachable.invalid",
        database="aicp",
    )

    engine = create_governance_engine(url)

    try:
        assert engine.dialect.name == "postgresql"
    finally:
        engine.dispose()


# 4. Exercise the connection check without requiring Docker.
def test_connection_check_with_sqlite():
    engine = create_engine("sqlite+pysqlite:///:memory:")

    try:
        assert check_database_connection(engine) is True
    finally:
        engine.dispose()
