# Policy Versioning and Governance Control Mapping 

## Purpose

Extend AI authorization evidence with reported policy version identifiers and internal governance control references.

## Policy version

Current policy identifier: `model-access/v1`

OPA includes this version in its authorization decision response.

The Python policy client validates the reported version. Older mocked responses without version information remain temporarily compatible and produce `not_reported` evidence.

## Internal governance control catalog

| Control ID | Description |
|---|---|
| AICP-AC-001 | Application-to-model authorization |
| AICP-RT-001 | Trusted model routing |
| AICP-FC-001 | Fail-closed policy evaluation |
| AICP-EV-001 | Evidence committed before inference |

These are internal project controls, not official compliance certifications.

## Evidence metadata

The `policy_evidence` table includes:

- `policy_version`: policy version reported by the decision service, or `not_reported`
- `control_ids`: JSON array of relevant internal governance control IDs

New records derive control references from validated decision reason codes.

## Schema migration

Existing SQLite evidence records are retained.

New columns are added when absent. Historical records receive the defaults:

- `policy_version = not_reported`
- `control_ids = []`

Historical evidence is not retroactively attributed to a new policy version.

## Enforcement

All previously established controls remain active:

1. Authenticate the calling application.
2. Evaluate authorization using OPA.
3. Verify the approved provider route.
4. Commit governance evidence, including available metadata.
5. Forward the request only after successful commit.

Unmapped governance reasons fail evidence persistence rather than silently storing unsupported mappings.

## Security limitations

- A self-reported policy version is not proof of the precise policy source that executed.
- No cryptographic policy digest or signature is stored.
- Older mocked decisions can temporarily omit version information.
- Internal control references do not prove compliance with external regulatory frameworks.
- Governance evidence remains in a local SQLite database.
- Policy and control catalog updates require coordinated deployment.

## Next steps

1. Require explicit version metadata for every successful authorization.
2. Include verifiable policy artifact digests.
3. Link internal controls to reviewed external framework requirements.
4. Introduce evidence verification and export capabilities.
5. Expand persistence beyond a single development gateway.