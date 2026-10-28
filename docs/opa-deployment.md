# Open Policy Agent Deployment — v0.1

## Purpose

Introduce Open Policy Agent (OPA) as the policy decision engine for the AI Control Plane.

## Architecture

The platform consists of three Docker Compose services:

| Service | Port | Responsibility |
|---|---|---|
| gateway | 8000 | FastAPI authentication, authorization and inference routing |
| mock-provider | 8001 | Deterministic mock inference |
| opa | 8181 | Policy evaluation API |

Only the gateway's port is published to the host, bound to localhost.

OPA and the mock provider are available inside the development Compose network.

## OPA Configuration

- Image: `openpolicyagent/opa:1.21.4`
- Mode: REST API server
- Internal address: `http://opa:8181`
- Health endpoint: `/health`
- Data endpoint: `/v1/data`
- Filesystem: read-only
- Linux capabilities: dropped
- Privilege escalation: disabled

## Gateway Configuration

The gateway receives the following environment variable:

`OPA_URL=http://opa:8181`

This variable is reserved for the future policy client.

## Current State

OPA is deployed and reachable from the gateway container.

No Rego authorization policies are loaded.

Runtime model authorization continues to use the Python model registry and application allowlist.

OPA does not currently authorize or deny inference requests.

## Security Considerations

OPA's API has management capabilities and must not be made accessible to untrusted clients.

For this MVP:

- Do not publish port 8181 to the host.
- Do not expose OPA on the public internet.
- Do not send prompts or API credentials to OPA.
- Do not use unknown policy results as authorization.
- Keep untrusted application containers off networks that can reach OPA's management API.

The shared development network is not sufficient isolation for a production deployment. Additional network separation and API access controls will be needed.

## Verification

Start the services:

`docker compose up --build -d`

Check containers:

`docker compose ps`

Check OPA logs:

`docker compose logs opa`

Verify that the gateway can make an HTTP GET request to `http://opa:8181/health` and receives status 200.

## Next Steps

1. Define model authorization rules in Rego.
2. Add Rego policy unit tests.
3. Implement a Python HTTPX policy client.
4. Enforce decisions in the gateway.
5. Fail closed when OPA is unavailable or returns an invalid decision.
6. Associate policy decisions with governance controls and audit evidence.