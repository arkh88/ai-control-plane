# Rego Model Authorization Policy — v0.1

## Purpose

Use Open Policy Agent to evaluate application-to-model authorization decisions.

## Policy files

- Runtime policy: `policies/model_access.rego`
- Unit tests: `policy_tests/model_access_test.rego`

## Package and decision

The policy package is `aicp.authz`.

The decision endpoint is:

`POST /v1/data/aicp/authz/decision`

Input fields:

- `application_id`: trusted authenticated application identifier
- `model_id`: requested registered model identifier

Output fields:

- `allow`: boolean authorization decision
- `reason`: stable explanation code

## Default-deny behavior

The policy defaults to `allow: false`.

Access is granted only when both conditions are met:

1. The model is registered.
2. The application is explicitly authorized for that model.

## Reason codes

| Reason | Meaning |
|---|---|
| ALLOW | Authorized model access |
| MODEL_NOT_ALLOWED | Registered application lacks permission |
| UNKNOWN_APPLICATION | Application is not registered |
| MODEL_NOT_REGISTERED | Model is unknown or missing |

## Testing

Run Rego tests using the pinned OPA Docker image:

`docker run --rm -v "$PWD/policies:/policies:ro" -v "$PWD/policy_tests:/policy_tests:ro" openpolicyagent/opa:1.21.4 test --fail-on-empty -v /policies /policy_tests`

Ten unit tests cover approved access, denied access, unknown applications, unknown models, and missing request attributes.

## Current enforcement status

OPA evaluates the authorization policy independently.

The FastAPI gateway still uses the Python authorization logic introduced on Day 13.

The two policy definitions currently duplicate the same permissions and must remain aligned until runtime integration is completed.

## Security limitations

- Model permissions are static.
- The policy assumes that application identity was authenticated upstream.
- OPA is not yet part of the gateway's inference enforcement path.
- Policy decisions are not yet persisted as governance evidence.
- OPA API management endpoints require stronger isolation for production.

## Next milestone

On Day 17, create an HTTPX OPA client and begin integrating policy evaluation with the gateway.

Policy failures and invalid responses must not grant access.

The gateway must remain responsible for enforcement.