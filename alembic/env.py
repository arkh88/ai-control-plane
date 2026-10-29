"""Alembic environment for the PostgreSQL governance database."""

from logging.config import fileConfig

from alembic import context
from app.governance_db import (
    create_governance_engine,
    database_url_from_env,
)
from app.governance_models import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Empty on Day 24.
# Day 25 will provide SQLAlchemy model metadata.
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Generate SQL without connecting to the database."""

    url = database_url_from_env()

    context.configure(
        url=url.render_as_string(hide_password=False),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Apply migrations using an actual database connection."""

    # Tests may supply an already-open SQLAlchemy connection.
    connection = config.attributes.get("connection")

    if connection is not None:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()

        return

    # Normal development deployment uses PostgreSQL.
    engine = create_governance_engine(database_url_from_env())

    try:
        with engine.connect() as connection:
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
            )

            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
