# Access-Control Security Test Matrix

**Project:** AI Control Plane  
**Version:** v0.1 development  
**Coverage:** Authentication and model authorization

## Objective

Verify that unauthenticated and unauthorized requests cannot trigger model inference through the gateway.

## Security invariants

**INV-001 — Authentication required**

Protected inference requests must have valid application credentials.

**INV-002 — Explicit model authorization**

Authenticated applications may access only models permitted by the server-side registry.

**INV-003 — No forbidden inference**

A rejected request must never be forwarded to the model provider.

**INV-004 — Fail closed**

Missing or invalid authentication configuration must prevent inference.

**INV-005 — Trusted identity**

Application identity must come from verified credentials and trusted server configuration, not client-supplied identity headers.

## Security verification matrix

| ID | Scenario | Expected status | Provider calls |
|---|---|---|---|
| SEC-001 | Valid key, approved model | 200 | 1 |
| SEC-002 | Missing key | 401 | 0 |
| SEC-003 | Incorrect key | 401 | 0 |
| SEC-004 | Unsupported authorization scheme | 401 | 0 |
| SEC-005 | Missing authentication configuration | 503 | 0 |
| SEC-006 | Previous credential after configured key rotation | 401 | 0 |
| SEC-007 | Unknown application identity | 403 | 0 |
| SEC-008 | Spoofed application identity header | 403 | 0 |

## Test implementation

File: `tests/test_security_regression.py`

Execute:

`python -m pytest tests/test_security_regression.py -v`

Tests use FastAPI dependency overrides, HTTPX MockTransport, and pytest monkeypatching.

No real model provider or external network is required.

## Current limitations

- One configured application credential per gateway instance.
- No credential expiration or revocation database.
- No OPA-based authorization.
- No data-classification policies.
- No governance evidence persistence.
- No protection against direct access to a reachable model endpoint.
- No runtime rate limiting.
- No independent deployment-level penetration testing.

## Future work

Integrate Open Policy Agent and connect decisions to governance control identifiers.

Expand the same security testing pattern to verify that:

1. Policy evaluation failures prevent inference.
2. Unauthorized data-classification routes are blocked.
3. Evidence-storage failures prevent approved requests from executing.
4. Governance events accurately describe the enforced decision.

## Exit criteria

All authentication and model authorization security regression tests pass locally and in GitHub Actions.

A passing test suite demonstrates the tested properties under the test configuration, not comprehensive security assurance.