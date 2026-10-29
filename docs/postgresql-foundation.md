# PostgreSQL and SQLAlchemy Foundation

## Goal

Introduce PostgreSQL and SQLAlchemy for the future normalized governance data model without modifying the existing inference authorization or SQLite evidence-persistence path.

## Implementation

- PostgreSQL 17 runs as an internal Docker Compose service.
- The database uses a named Docker volume for persistent storage.
- PostgreSQL has no host-published port.
- The database password is stored in a Git-ignored local `.env` file.
- Python uses SQLAlchemy 2.0 with the Psycopg 3 driver.
- The connection layer lives in `app/governance_db.py`.
- Database connections are established only when explicitly requested.

## Verification

Four new Python tests validate configuration, URL handling, lazy engine creation and the connection-check helper.

The Docker integration test confirms SQLAlchemy can connect to the live PostgreSQL database.

Existing gateway, OPA, Rego and SQLite evidence tests remain unchanged.

PostgreSQL unavailability must not affect the existing inference path during this transitional phase.

## Security and limitations

PostgreSQL is a development-only governance database and currently has no application tables.

No API keys, prompts, model responses or authorization evidence are migrated today.

The current SQLite commit-before-inference guarantee remains active.

PostgreSQL has no published host port, but further network segmentation and credential hardening are future tasks.

## Next milestone

Day 24: Configure Alembic and implement repeatable baseline database migrations.

The PostgreSQL database will not become the authoritative evidence store until the later, tested cutover milestone.