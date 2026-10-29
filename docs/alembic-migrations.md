# Day 24 — Alembic Migration Foundation

## Objective

Introduce version-controlled database migrations for the PostgreSQL governance data model without changing the existing SQLite evidence or inference enforcement path.

## Implementation

- Alembic 1.20.1
- Configuration: `alembic.ini`
- Migration environment: `alembic/env.py`
- Initial revision: `0001_governance_baseline`
- Database connection configuration: `app/governance_db.py`

## Baseline migration

The initial revision does not create application tables.

It establishes Alembic version tracking through the `alembic_version` table.

Application, credential and model tables will be introduced through a subsequent migration on Day 25.

## Configuration and security

Database credentials are obtained from the existing trusted environment configuration.

No password is stored in `alembic.ini`.

Migration execution is a separate operational process and is not triggered automatically by an inference request.

## Verification

Four Python tests cover migration discovery, upgrading a fresh database, repeatable upgrades without data loss, and downgrade/re-upgrade behavior on a disposable database.

A separate live PostgreSQL check applies the migration twice against a disposable database and verifies its recorded revision.

The approved baseline is then applied to the development governance database.

## Invariants preserved

- OPA remains the authority for model authorization.
- Unknown or denied models cannot reach inference.
- The gateway still commits SQLite evidence before approved inference.
- PostgreSQL is not yet required for inference.
- No existing SQLite evidence is migrated or removed.

## Next milestone

Day 25 will implement the `applications`, `api_credentials`, and `models` tables through a new Alembic revision.

Schema migrations must continue to be reviewed before execution, and existing development data must not be silently discarded.