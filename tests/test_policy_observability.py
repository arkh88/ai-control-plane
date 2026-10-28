"""Regression tests for policy logs and correlation IDs."""

import hashlib
import json
from uuid import UUID

import httpx
import pytest
from fastapi.testclient import TestClient

from app import policy_audit
from app.auth import require_application
from app.main import app
from app.policy_client import get_policy_client
from app.provider_client import get_provider_client

client = TestClient(app)


def payload(model="local-small", content="Hello"):
    return {
        "model": model,
        "messages": [{"role": "user", "content": content}],
        "stream": False,
    }


@pytest.fixture
def audit_lab(monkeypatch):
    events = []
    provider_calls = []

    state = {"opa_handler": None}

    # Capture JSON records produced by the real logging function.
    def capture_log(message):
        events.append(json.loads(message))

    monkeypatch.setattr(
        policy_audit.audit_logger,
        "info",
        capture_log,
    )

    def opa_handler(request):
        custom_handler = state["opa_handler"]

        if custom_handler is not None:
            return custom_handler(request)

        return httpx.Response(
            200,
            json={
                "result": {
                    "allow": True,
                    "reason": "ALLOW",
                }
            },
        )

    def provider_handler(request):
        provider_calls.append(request)
        forwarded = json.loads(request.content)

        return httpx.Response(
            200,
            json={
                "id": "chatcmpl-day19",
                "object": "chat.completion",
                "created": 1700000000,
                "model": forwarded["model"],
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": "Mock response",
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": None,
            },
        )

    async def override_policy_client():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(opa_handler),
            base_url="http://opa:8181",
            trust_env=False,
        ) as opa:
            yield opa

    async def override_provider_client():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(provider_handler),
            base_url="http://mock-provider:8001",
            trust_env=False,
        ) as provider:
            yield provider

    monkeypatch.setitem(
        app.dependency_overrides,
        get_policy_client,
        override_policy_client,
    )

    monkeypatch.setitem(
        app.dependency_overrides,
        get_provider_client,
        override_provider_client,
    )

    return {
        "events": events,
        "provider_calls": provider_calls,
        "state": state,
    }


# 1. Approved requests have one correlated policy log.
def test_allowed_request_has_correlated_log(audit_lab):
    response = client.post(
        "/v1/chat/completions",
        json=payload(),
    )

    assert response.status_code == 200
    assert len(audit_lab["provider_calls"]) == 1
    assert len(audit_lab["events"]) == 1

    event = audit_lab["events"][0]

    assert event["event"] == "policy_decision"
    assert event["application_id"] == "test-app"
    assert event["model_id"] == "local-small"
    assert event["outcome"] == "allow"
    assert event["reason"] == "ALLOW"
    assert event["policy_engine"] == "opa"
    assert event["timestamp"]
    assert event["request_id"] == response.headers["X-Request-ID"]
    assert UUID(event["request_id"]).version == 4


# 2. Denied model access is logged and never forwarded.
def test_denied_request_is_logged(audit_lab):
    audit_lab["state"]["opa_handler"] = lambda request: httpx.Response(
        200,
        json={
            "result": {
                "allow": False,
                "reason": "MODEL_NOT_ALLOWED",
            }
        },
    )

    response = client.post(
        "/v1/chat/completions",
        json=payload("restricted-small"),
    )

    assert response.status_code == 403
    assert audit_lab["provider_calls"] == []
    assert len(audit_lab["events"]) == 1

    event = audit_lab["events"][0]
    assert event["outcome"] == "deny"
    assert event["reason"] == "MODEL_NOT_ALLOWED"
    assert event["request_id"] == response.headers["X-Request-ID"]


# 3. OPA timeouts produce an error event.
def test_opa_timeout_is_logged(audit_lab):
    def timeout(request):
        raise httpx.ReadTimeout(
            "Simulated timeout",
            request=request,
        )

    audit_lab["state"]["opa_handler"] = timeout

    response = client.post(
        "/v1/chat/completions",
        json=payload(),
    )

    assert response.status_code == 503
    assert audit_lab["provider_calls"] == []
    assert len(audit_lab["events"]) == 1
    assert audit_lab["events"][0]["outcome"] == "error"
    assert audit_lab["events"][0]["reason"] == ("POLICY_EVALUATION_ERROR")


# 4. An upstream OPA HTTP failure is logged.
def test_opa_http_error_is_logged(audit_lab):
    audit_lab["state"]["opa_handler"] = lambda request: httpx.Response(
        503, json={"error": "Unavailable"}
    )

    response = client.post(
        "/v1/chat/completions",
        json=payload(),
    )

    assert response.status_code == 503
    assert audit_lab["provider_calls"] == []
    assert len(audit_lab["events"]) == 1
    assert audit_lab["events"][0]["reason"] == ("POLICY_EVALUATION_ERROR")


# 5. Malformed decisions are logged as errors.
def test_invalid_opa_decision_is_logged(audit_lab):
    audit_lab["state"]["opa_handler"] = lambda request: httpx.Response(
        200,
        json={
            "result": {
                "allow": "true",
                "reason": "ALLOW",
            }
        },
    )

    response = client.post(
        "/v1/chat/completions",
        json=payload(),
    )

    assert response.status_code == 503
    assert audit_lab["provider_calls"] == []
    assert audit_lab["events"][0]["outcome"] == "error"


# 6. Missing OPA result also produces an error event.
def test_missing_opa_result_is_logged(audit_lab):
    audit_lab["state"]["opa_handler"] = lambda request: httpx.Response(200, json={})

    response = client.post(
        "/v1/chat/completions",
        json=payload(),
    )

    assert response.status_code == 503
    assert audit_lab["provider_calls"] == []
    assert len(audit_lab["events"]) == 1
    assert audit_lab["events"][0]["reason"] == ("POLICY_EVALUATION_ERROR")


# 7. Unavailable registered routes are logged as errors.
def test_route_failure_is_logged(audit_lab):
    response = client.post(
        "/v1/chat/completions",
        json=payload("unregistered-model"),
    )

    # Fake OPA allows; local route validation must still reject.
    assert response.status_code == 503
    assert audit_lab["provider_calls"] == []
    assert len(audit_lab["events"]) == 1
    assert audit_lab["events"][0]["outcome"] == "error"
    assert audit_lab["events"][0]["reason"] == "ROUTE_UNAVAILABLE"


# 8. IDs are unique and sensitive values stay out of our logs.
def test_unique_ids_and_no_sensitive_policy_logs(audit_lab):
    secret = "DAY19_FAKE_SECRET_MARKER"
    private_prompt = "DAY19_PRIVATE_PROMPT_MARKER"

    responses = [
        client.post(
            "/v1/chat/completions",
            json=payload(content=private_prompt),
            headers={
                "Authorization": f"Bearer {secret}",
                "X-Request-ID": "caller-controlled-id",
            },
        )
        for _ in range(2)
    ]

    assert all(response.status_code == 200 for response in responses)
    assert len(audit_lab["provider_calls"]) == 2
    assert len(audit_lab["events"]) == 2

    ids = [r.headers["X-Request-ID"] for r in responses]

    assert ids[0] != ids[1]
    assert "caller-controlled-id" not in ids
    assert [e["request_id"] for e in audit_lab["events"]] == ids

    serialized_events = json.dumps(audit_lab["events"])
    assert secret not in serialized_events
    assert private_prompt not in serialized_events
    assert "authorization" not in serialized_events.lower()


# 9. Authentication failures still get correlation IDs,
#    but do not generate an OPA decision event.
def test_missing_auth_has_id_without_policy_event(audit_lab, monkeypatch):
    monkeypatch.delitem(
        app.dependency_overrides,
        require_application,
        raising=False,
    )

    test_key = "day19-test-key"
    monkeypatch.setenv(
        "AICP_API_KEY_SHA256",
        hashlib.sha256(test_key.encode()).hexdigest(),
    )
    monkeypatch.setenv("AICP_APP_ID", "demo-app")

    response = client.post(
        "/v1/chat/completions",
        json=payload(),
    )

    assert response.status_code == 401
    assert UUID(response.headers["X-Request-ID"]).version == 4
    assert audit_lab["events"] == []
    assert audit_lab["provider_calls"] == []
