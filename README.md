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

## Docker Development

Build the application image:

```bash
docker build -t ai-control-plane:day6 .
```

Run the API:

```bash
docker run --rm \
  --name ai-control-plane-day6 \
  -p 127.0.0.1:8000:8000 \
  ai-control-plane:test
```

Test the health endpoint:

```bash
curl http://127.0.0.1:8000/health/live
```

Interactive API documentation:

http://127.0.0.1:8000/docs

The container runs as a non-root user.

The API is bound to localhost on the host machine.
Do not expose this development configuration publicly.

## Development Quality Checks

Run the application:

    docker compose up --build -d

Check the application:

    curl http://127.0.0.1:8000/health/live

Stop the application:

    docker compose down

Run linting and formatting checks:

    ruff check app tests
    ruff format --check app tests

Run automated tests:

    python -m pytest -v

CI checks are defined in .github/workflows/ci.yml.

## Chat Completions API

Endpoint: POST /v1/chat/completions

MVP v0.1 contract:
- Text-only messages
- Non-streaming requests
- Required registered-model identifier
- Strict Pydantic input validation
- OpenAI-compatible response schema subset

Current behavior:
- Valid requests return HTTP 501 until Day 9
- Invalid requests return HTTP 422

Authentication, policy enforcement, and model routing
are not implemented yet.

Do not expose this development endpoint publicly.

## Mock AI Provider

The project includes a deterministic mock inference provider.

Location: `app/mock_provider.py`

The mock provider:
- Accepts text-only chat completion requests.
- Reuses the gateway's Pydantic request schema.
- Returns predictable assistant responses.
- Requires no GPU or external AI API.
- Does not echo prompt content.
- Runs as a separate Docker Compose service.

Its completion identifiers and timestamps are fixed
test fixtures, not production audit identifiers.

Start services:

    docker compose up --build -d

Check containers:

    docker compose ps

Stop services:

    docker compose down

The mock provider listens on port 8001 inside
the Compose network but is not published to the host.

The gateway-to-provider connection will be
implemented on Day 10.