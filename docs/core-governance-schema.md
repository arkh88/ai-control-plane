# Day 25 — Core Governance Registration Schema

## Objective

Implement the first three relational governance tables using SQLAlchemy ORM models and an Alembic migration.

## Tables

### applications

Registers application identifiers, human-readable names and active status.

The primary key is `application_id`, aligned with the identifier used by the existing gateway.

### api_credentials

Stores credential identifiers, trusted application references, SHA-256 credential digests, active status and creation timestamps.

The table contains no plaintext API-key column.

Constraints include:
- Primary key for credential identity
- Foreign key to the registered application
- Unique credential digest
- 64-character digest-length check
- Application lookup index

The credential digest is not yet used by the live authentication flow. Future insertion logic must validate digest format, use high-entropy credentials and implement revocation safely.

### models

Registers logical model IDs, approved provider identifiers and active status.

The database does not accept arbitrary provider URLs as part of the model registration schema.

## Migration

Revision: `0002_core_governance_tables`

Parent revision: `0001_governance_baseline`

The migration creates the tables in dependency-safe order and includes a downgrade for disposable development databases.

## Verification

- SQLAlchemy ORM relationship tests
- Primary-key uniqueness checks
- Credential digest uniqueness and length checks
- Foreign-key integrity checks
- Alembic migration chain verification
- Fresh PostgreSQL upgrade and repeated-upgrade verification

## Current security boundary

These tables are not yet authoritative for inference.

Application authentication and model routing still use trusted server-side configuration.

OPA remains responsible for authorization.

SQLite remains the active evidence store, and its commit-before-inference requirement is unchanged.

## Next step

Day 26: review migrations, create safe development-only seed data, verify repeatable fresh database setup, and address schema inconsistencies before implementing governance control and policy tables.