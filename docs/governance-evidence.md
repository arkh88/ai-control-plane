# Governance Decision Evidence — Day 20

## Purpose

Persist authorization and enforcement outcomes before the gateway permits model inference.

## Evidence schema

Each record includes:

- Unique evidence ID
- Gateway-generated request ID
- UTC timestamp
- Trusted application identity
- Requested model identifier
- Effective enforcement outcome
- Decision or failure reason
- Logical policy reference

## Enforcement guarantee

For requests that reach OPA evaluation, the gateway must successfully commit an evidence record before forwarding to the model provider.

If evidence storage fails, the gateway returns HTTP 503 and does not execute inference.

OPA denials and evaluation failures are also recorded when storage is available.

Requests rejected before OPA evaluation, such as authentication failures, are not covered by this evidence path yet.

## Storage

The local MVP uses SQLite with transactional inserts and synchronous FULL mode.

The database is stored on a host-mounted development directory and excluded from Git.

Records are inserted rather than silently overwritten. Request IDs have a uniqueness constraint.

## Evidence outcomes

- `allow`: OPA allowed access and a valid route was found.
- `deny`: OPA explicitly denied access.
- `error`: Policy evaluation failed or the approved route was unavailable.

An `allow` event records authorization approval, not successful inference.

## Security and privacy

Evidence excludes raw API keys, Authorization headers, prompts, and model outputs.

SQLite is used only as a local development persistence mechanism.

## Current limitations

- No tamper-evident hash chain or digital signatures
- No independently verified OPA policy revision
- No database access-control separation
- No guaranteed off-host replication or backup
- No formal retention policy
- No database migration framework
- No governance control identifier mapping
- No evidence for authentication failures
- No separate inference completion event
- Synchronous SQLite writes are not appropriate for high-concurrency production use

The policy reference identifies the logical decision rule but does not prove which exact policy version executed.

## Future direction

Introduce versioned governance evidence, policy revision identifiers, append-only or tamper-evident storage, control mappings, and a scalable evidence persistence service.

These controls will strengthen independent verification of security decisions.