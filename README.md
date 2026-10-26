# AI Control Plane

An open-source platform for AI runtime security enforcement and governance evidence.

## Mission

Enable organizations to securely deploy AI applications by enforcing authorization policies and generating auditable governance evidence.

## MVP v0.1

- Authenticate AI applications.
- Authorize access to approved AI models.
- Enforce security policies using Open Policy Agent.
- Store evidence of policy decisions.
- Link technical controls to governance objectives.
- Export and verify audit evidence.

## Technology

Python, FastAPI, Open Policy Agent, PostgreSQL, pytest, Docker Compose.

## First Release Goal

Demonstrate an allowed AI request, a denied AI request, and verifiable governance evidence linked to the applied security policy.

## Local Development

Create and activate a Python virtual environment,
then install dependencies:

```bash
python -m pip install -r requirements.txt
```

Start the development server:

```bash
uvicorn app.main:app --reload --host 127.0.0.1
```

Endpoints:

- GET /health/live — application liveness
- GET /docs — interactive OpenAPI documentation

The service currently has no authentication
or model inference capabilities.

## Automated Testing

The project uses pytest and FastAPI TestClient.

Install dependencies:

    python -m pip install -r requirements.txt

Run all tests:

    python -m pytest -v

Current tests cover:
- API liveness response
- Health response schema
- JSON content type
- Unknown endpoint handling

Future tests will cover:
- Application authentication
- OPA authorization
- Fail-closed policy enforcement
- Model routing
- Governance evidence integrity