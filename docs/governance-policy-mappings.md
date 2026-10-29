# Day 27 — Relational Governance Policy Mapping

## Purpose

Extend the PostgreSQL governance data model with internal controls, reported policy versions, and decision-reason-to-control mappings.

## New tables

### controls

Stores internal control identifiers and objectives.

Existing internal identifiers include `AICP-AC-001`, `AICP-RT-001`, `AICP-FC-001`, and `AICP-EV-001`.

These are project-specific controls, not external regulatory certifications.

### policy_versions

Stores the reported policy version, logical OPA policy reference, and description.

The current reported policy is `model-access/v1`, referencing `aicp.authz.decision`.

A reported version is not cryptographically verified policy provenance.

### policy_control_mappings

Links a policy version and an OPA decision reason to an internal control.

The composite primary key prevents duplicate mappings. Foreign keys require valid policy versions and control identifiers. Deletion of referenced parent records is restricted.

Only actual OPA decision reasons are mapped here. Gateway-generated evaluation and route errors remain handled by the existing Python control catalog.

## Migration

Revision: `0003_policy_control_mappings`

Parent: `0002_core_governance_tables`

The revision creates three new tables and one control lookup index.

Existing governance registration tables and SQLite decision evidence are not modified.

## Verification

- Schema and foreign-key inspection
- Mapping consistency with the Day 22 control catalog
- Rejection of unregistered policy versions and controls
- Duplicate mapping rejection
- Separation of mappings by policy version
- Restricted deletion of referenced policy versions
- Live PostgreSQL mapping persistence with transaction rollback
- Alembic schema-drift verification in GitHub Actions

## Current limitations

The relational tables are not yet populated as authoritative runtime configuration.

No automatic synchronization currently exists between Python's control catalog, the Rego policy, and the new PostgreSQL mapping tables.

These tables do not establish external regulatory compliance.

Policy artifact SHA-256 verification remains scheduled for Day 31.

## Next milestone

Day 28: Implement a PostgreSQL decisions table and repository operations. Design references to policy versions and governance mappings carefully, while preserving the current SQLite commit-before-inference guarantee until the controlled cutover.