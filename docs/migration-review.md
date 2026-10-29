# Day 26 — Governance Database Migration Review

## Objective

Verify that the governance database schema matches its SQLAlchemy models, PostgreSQL migrations are repeatable, and temporary development records can be discarded safely.

## Review findings

The Alembic environment previously used empty metadata. It now imports `Base.metadata` from the governance ORM models.

A separate PostgreSQL integration job has been added to GitHub Actions.

## Verification coverage

- ORM metadata matches the schema produced by Alembic revisions 0001 and 0002.
- Unexpected schema tables are detected during drift checks.
- Repeated upgrades preserve the current migration revision.
- The PostgreSQL database contains `applications`, `api_credentials`, `models`, and `alembic_version`.
- Temporary application, model, and credential records can be rolled back.
- CI uses an isolated PostgreSQL service and disposable credentials.
- No real credentials are seeded into the development governance database.

## Data retention and cleanup

Automated tests use isolated, disposable databases or transaction rollback.

Local demonstration databases can be deleted after testing.

The main development PostgreSQL database and its Alembic version history are retained.

Existing SQLite evidence is not needed as accumulated demonstration data, but the active SQLite evidence persistence implementation remains necessary until the PostgreSQL cutover.

## Security boundaries

PostgreSQL governance registration tables are not yet authoritative for authentication or model routing.

OPA authorization, fixed provider routing, and SQLite commit-before-inference remain unchanged.

Schema drift checks are useful development controls, not a substitute for database access controls, reviewed migrations, backups, or production change management.

## Next milestone

Day 27: Create the `controls`, `policy_versions`, and governance control mapping tables.

Implement their ORM relationships and Alembic migration while retaining the existing gateway authorization behavior.