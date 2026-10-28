# OPA Policy Client — v0.1

## Purpose

Provide a typed, fail-closed Python HTTP client for evaluating model-access policies through Open Policy Agent.

## Implementation

- Source: `app/policy_client.py`
- Tests: `tests/test_policy_client.py`
- Decision endpoint: `/v1/data/aicp/authz/decision`
- Configuration: `OPA_URL`
- HTTP library: HTTPX
- Validation library: Pydantic

## Input

The policy client accepts a trusted application identifier and a requested model identifier.

The application identifier must come from authenticated gateway context, not from arbitrary client-provided headers.

## Decision contract

A valid policy decision contains:

- `allow`: a JSON boolean
- `reason`: a recognized authorization reason

Supported reasons:

- `ALLOW`
- `MODEL_NOT_ALLOWED`
- `UNKNOWN_APPLICATION`
- `MODEL_NOT_REGISTERED`

Contradictory results are rejected.

## Failure behavior

The client raises `PolicyClientError` on:

- Connection failure
- Request timeout
- Upstream HTTP error
- Invalid JSON
- Missing decision result
- Invalid field types
- Unknown reason codes
- Contradictory authorization decisions

The policy client never converts an error into an allow decision.

## Current deployment state

The FastAPI gateway continues to enforce the Python model allowlist.

The new OPA policy client is independently tested and can query the deployed OPA service.

The inference endpoint does not yet call this client.

## Future enforcement requirements

Before forwarding an inference request, the gateway must:

1. Authenticate the calling application.
2. Evaluate the requested model using OPA.
3. Validate the returned policy decision.
4. Forward only an explicitly allowed request.
5. Block requests when OPA denies or evaluation fails.

The system must distinguish a policy denial from a policy-service failure without permitting either to bypass enforcement.

## Limitations

The initial client uses a two-second HTTP timeout and has no automatic retries or circuit breaker.

It does not yet emit governance evidence or policy-decision audit records.

OPA API network isolation, policy versioning, and decision correlation will require additional work before production use.