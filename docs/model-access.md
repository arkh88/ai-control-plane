# Model Access Control — v0.1

## Purpose

Enforce an explicit allowlist of AI models for authenticated applications.

## Authorization sequence

1. Authenticate the application using its API key.
2. Derive the application identity from trusted server configuration.
3. Verify that the requested model is registered.
4. Verify that the application is authorized for the model.
5. Resolve the model to its configured provider.
6. Forward only approved requests.

## Registered models

| Model | Provider | Authorized applications |
|---|---|---|
| local-small | mock-provider | demo-app, test-app, finance-assistant |
| restricted-small | mock-provider | finance-assistant |

## Security behavior

- Unregistered models return HTTP 404.
- Unauthorized model access returns HTTP 403.
- Missing or invalid API credentials return HTTP 401.
- Unauthorized requests must never reach the model provider.
- Client-supplied provider destinations are rejected.
- Applications without explicit permissions are denied by default.

## Architecture decisions

The MVP uses a static model registry and application allowlist implemented in Python.

Model names are logical identifiers. Both registered models currently use the deterministic mock provider.

The actual provider network destination is supplied through trusted deployment configuration.

## Limitations

- Authorization is not yet implemented using OPA.
- The system supports one deployed API credential.
- No runtime policy management is available.
- Governance evidence is not yet recorded.
- Administrative policy changes require code deployment.
- Network-level prevention of provider bypass is not yet fully enforced.

## Future integration

The model registry will remain responsible for identifying approved models and destinations.

Open Policy Agent will become the authorization decision engine, evaluating application identity, model registration, data classification, and deployment context.

Authorization decisions will eventually reference governance controls and produce durable audit evidence.