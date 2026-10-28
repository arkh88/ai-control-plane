# OPA Runtime Enforcement — Day 18

## Purpose

Make Open Policy Agent authorization mandatory before AI inference.

## Enforcement sequence

1. Validate the incoming inference request.
2. Authenticate the application using its API key.
3. Derive trusted application identity.
4. Evaluate the requested model using the OPA policy client.
5. Reject invalid, missing, or denied policy decisions.
6. Verify that approved models have a trusted registered provider route.
7. Forward the request to the mock provider.
8. Validate the provider response before returning it.

## Authorization contract

| Outcome | Gateway HTTP response |
|---|---|
| Authorized request with working provider | 200 |
| Model access denied | 403 |
| Model not registered according to OPA | 404 |
| OPA unavailable or malformed decision | 503 |
| Approved model has no valid local route | 503 |

## Fail-closed behavior

The inference endpoint must never call the model provider when:

- OPA denies the request.
- OPA times out.
- OPA is unreachable.
- OPA returns an HTTP error.
- OPA returns malformed authorization data.
- OPA omits the decision result.
- An approved model lacks a supported registered route.

The gateway does not fall back to the previous Python application allowlist.

## Responsibility separation

**Authentication:** FastAPI application credential validation.

**Authorization:** OPA Rego decision engine.

**Provider routing:** Trusted local model registry.

**Inference execution:** HTTPX provider client.

The Python application-to-model mapping may remain in test fixtures during migration, but is not a production authorization authority.

## Testing

Automated enforcement tests prove that denied and failed evaluations result in zero provider calls.

Live Docker integration verifies that the gateway honors OPA decisions and returns a policy-service error when OPA is stopped.

## Current limitations

- Policy decisions are not persisted as governance evidence.
- Provider routing supports only the configured mock provider.
- OPA policy and model-routing configurations are maintained separately.
- No production-grade OPA management API isolation is implemented.
- No policy decision version or request correlation identifier is recorded.
- No production load or resilience testing has been completed.

## Next steps

Add structured authorization decision logging, request identifiers, and policy decision evidence suitable for audit and governance-control mapping.