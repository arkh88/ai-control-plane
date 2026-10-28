# Policy Decision Observability — Day 19

## Purpose

Introduce structured operational logging and correlation IDs for OPA authorization decisions.

## Request correlation

The FastAPI gateway generates a UUIDv4 identifier for every HTTP request.

The identifier is stored in request state and returned to the caller using the `X-Request-ID` response header.

Client-provided request IDs are not trusted or reused.

## Structured policy event

Event name: `policy_decision`

Fields:

- `event`: event type
- `timestamp`: UTC time of logging
- `request_id`: gateway-generated correlation ID
- `application_id`: trusted authenticated identity
- `model_id`: requested logical model
- `policy_engine`: `opa`
- `outcome`: `allow`, `deny`, or `error`
- `reason`: decision or failure reason

## Logging rules

The gateway emits one event for each completed authorization evaluation or policy-routing check.

An allow event records authorization approval, not successful inference.

Authentication failures and invalid requests rejected before policy evaluation do not yet generate policy-decision events.

## Sensitive information

Policy events must not contain:

- API keys or Bearer tokens
- Authorization headers
- Prompt contents
- Model-generated responses
- Raw request or response bodies

## Failure behavior

OPA denial prevents inference and emits a denial event.

OPA evaluation failures prevent inference and emit an error event.

Approved models without a valid registered route also produce error events and cannot reach inference.

## Verification

Automated tests cover event fields, request-ID correlation, denied and failed requests, missing decisions, unique IDs, and sensitive-data exclusion.

Docker Compose logs provide a manual verification path for real operational output.

## Limitations

These logs are operational telemetry, not durable governance evidence.

They do not yet provide:

- Transactional persistence
- Tamper-evident storage
- Guaranteed delivery or retention
- Policy-version identifiers
- Governance control mappings
- Authentication failure events
- A complete model inference outcome trail

## Next milestone

Introduce structured governance decision evidence with stable event schemas, policy references, and reliable storage.

Before considering the system production-ready, evidence persistence and failure behavior must be explicitly designed and tested.