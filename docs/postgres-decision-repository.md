# Day 28 — PostgreSQL Decisions and Transactional Repository

## Objective

Create a durable PostgreSQL authorization decision table and a repository supporting atomic insertion and readback.

The existing SQLite evidence store remains authoritative for live inference through Day 28.

## Database schema

Alembic revision: `0004_governance_decisions`

Parent revision: `0003_policy_control_mappings`

The `decisions` table contains evidence ID, unique request ID, timestamp, application ID, model ID, outcome, decision reason, policy reference, reported policy version, and a JSON snapshot of governance control identifiers.

The schema stores no API keys, prompts, model responses, or client-provided provider URLs.

## Relational design

The decisions table does not require foreign keys to registered applications or models, allowing evidence for unregistered identities and model IDs.

Policy versions are stored as reported values, including `not_reported` when evaluation fails. They are not yet cryptographically attested.

Control IDs are stored as a decision-time snapshot derived from the validated internal governance control catalog.

## Transactional repository

Implementation: `app/decision_repository.py`

The `PostgresDecisionRepository` accepts the existing `EvidenceRecord` contract.

`write()` uses SQLAlchemy `engine.begin()`, returning after transaction commit.

Database failures and invalid mappings raise `DecisionRepositoryError`.

`get_by_request_id()` reads previously committed records.

## Verification

- Eight focused repository tests
- PostgreSQL round-trip integration test
- Duplicate request ID rejection
- Unsupported outcome rejection
- Unknown control reason rejection
- Successful persistence of denied or failed policy evaluations
- Database failure error handling
- Alembic schema-drift verification
- Full existing gateway, SQLite and Rego regression suites

## Security limitations

The repository is not yet wired into the inference gateway.

A successful database insert is not, by itself, proof that the full inference request path is fail-closed.

The table permits ordinary database administrators to update or delete records and is not tamper-evident.

Policy artifact provenance, audit hash chaining, and independent verification remain future milestones.

## Next milestone

Day 29: Perform a controlled cutover from SQLite to PostgreSQL decision persistence.

The cutover must preserve all existing security invariants, including durable commit before provider inference, policy-denial evidence, failure evidence, and blocking inference on database failure.

Existing SQLite evidence must not be silently discarded.