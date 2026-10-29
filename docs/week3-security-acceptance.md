# Week 3 — Fail-Closed Security Acceptance

## Purpose

Verify the integrated security enforcement behavior of the AI Governance & Security Control Plane.

## Security architecture

The inference gateway enforces the following sequence:

1. Validate the API request.
2. Authenticate the calling application.
3. Evaluate model authorization through OPA.
4. Verify the approved model's trusted provider route.
5. Persist governance decision evidence.
6. Commit the evidence transaction.
7. Forward the approved inference request.

Any failed required control must prevent inference.

## Security invariants

**INV-001 — Authentication:** Requests without valid credentials cannot reach OPA or inference.

**INV-002 — Authorization:** Explicit OPA denials cannot reach inference.

**INV-003 — Policy availability:** OPA errors, timeouts and malformed decisions cannot grant access.

**INV-004 — Trusted routing:** OPA approval alone cannot create an unknown model route.

**INV-005 — Evidence-before-inference:** Successful evidence commit is required before an approved provider request is sent.

**INV-006 — Distinct outcomes:** Authorization approval and inference success are different facts. Provider failures do not invalidate previously committed authorization evidence.

## Automated verification

The acceptance tests are implemented in:

`tests/test_fail_closed_e2e.py`

They cover:

- Successful ordered enforcement
- Missing authentication
- Explicit OPA denial
- Unregistered models
- OPA timeout
- Malformed policy decisions
- Invalid provider routes
- Evidence commit failures
- Provider HTTP failure after approval
- Provider timeout after approval

The tests use real FastAPI authentication and evidence-writing logic, with controlled HTTPX transports for OPA and the provider.

## Docker integration

A controlled OPA shutdown verifies that the gateway returns HTTP 503 for an otherwise authorized inference request.

The corresponding error evidence is checked in SQLite using the gateway-generated request ID.

OPA is restarted after verification.

## Acceptance criteria

- All Python tests pass.
- All Rego policy tests pass.
- Ruff checks pass.
- No inference request bypasses required enforcement controls in the tested scenarios.
- Failure evidence is committed when the evidence store is available.
- GitHub Actions passes.

## Limitations

These tests do not constitute a production security certification or independent penetration test.

The current platform still lacks:

- Tamper-evident evidence storage
- Cryptographically verified policy revisions
- Governance control mappings
- Production-grade evidence retention and backups
- Full network isolation of OPA management endpoints
- A separate inference-outcome evidence lifecycle
- High-concurrency and distributed failure testing
- Atomic coordination between evidence storage and external model execution

SQLite transaction success proves the local record was committed before the observed provider call. It does not guarantee exactly-once inference delivery or eliminate every crash-related failure window.

## Next milestone

Extend governance evidence with policy versions, control references, and stronger audit verification capabilities.