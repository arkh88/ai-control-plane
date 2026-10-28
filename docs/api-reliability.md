# AI Gateway API Reliability — v0.1

## Purpose

Document the reliability behavior of the AI Control
Plane's inference gateway.

## Endpoint

POST /v1/chat/completions

## Supported Behavior

- Validate requests using Pydantic.
- Forward valid requests to the configured provider.
- Validate provider responses before returning them.
- Return controlled errors on provider failure.
- Never allow callers to select arbitrary provider URLs.
- Do not automatically retry inference requests.

## Error Contract

| Condition | HTTP Status |
|---|---|
| Successful inference | 200 |
| Invalid input | 422 |
| Provider HTTP error | 502 |
| Invalid provider response | 502 |
| Provider timeout | 504 |

## Current Security Limitations

The gateway does not yet implement:

- Application authentication
- OPA authorization
- Model allowlists
- Governance evidence persistence
- Per-application rate limits

This version is for local development only.

## Planned Security Controls

Future milestones will introduce:

1. Authenticated application identity.
2. Registered model destinations.
3. Policy-as-code authorization.
4. Durable authorization evidence.
5. Fail-closed behavior on policy or audit failures.

## Testing

Integration tests use HTTPX MockTransport.

Test coverage includes:

- Correct request forwarding
- Invalid request rejection
- Malformed provider responses
- Invalid provider JSON
- Provider HTTP errors
- Provider timeouts

Tests must not depend on live providers, external
network connections, or a running Docker environment.