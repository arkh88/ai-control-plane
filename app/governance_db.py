"""PostgreSQL connectivity for the governance data model.

Day 23: connectivity only. No inference-path database cutover.
"""

import os

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import URL

REQUIRED_SETTINGS = (
    "AICP_GOVERNANCE_DB_HOST",
    "AICP_GOVERNANCE_DB_USER",
    "AICP_GOVERNANCE_DB_PASSWORD",
    "AICP_GOVERNANCE_DB_NAME",
)


def database_url_from_env() -> URL:
    """Build a PostgreSQL URL from trusted server configuration."""

    missing = [name for name in REQUIRED_SETTINGS if not os.getenv(name)]

    if missing:
        raise RuntimeError(
            "Missing governance database configuration: " + ", ".join(missing)
        )

    return URL.create(
        drivername="postgresql+psycopg",
        username=os.environ["AICP_GOVERNANCE_DB_USER"],
        password=os.environ["AICP_GOVERNANCE_DB_PASSWORD"],
        host=os.environ["AICP_GOVERNANCE_DB_HOST"],
        port=5432,
        database=os.environ["AICP_GOVERNANCE_DB_NAME"],
        query={"connect_timeout": "3"},
    )


def create_governance_engine(url: URL) -> Engine:
    """Construct a SQLAlchemy engine without opening a connection."""

    return create_engine(
        url,
        pool_pre_ping=True,
    )


def check_database_connection(engine: Engine) -> bool:
    """Verify database connectivity using a simple SQL query."""

    with engine.connect() as connection:
        result = connection.scalar(text("SELECT 1"))

    return result == 1
