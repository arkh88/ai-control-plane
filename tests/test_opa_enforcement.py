"""Fail-closed gateway enforcement tests."""

import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.policy_client import get_policy_client
from app.provider_client import get_provider_client

client = TestClient(app)


def payload(model="local-small"):
    return {
        "model": model,
        "messages": [{"role": "user", "content": "Day 18 test"}],
        "stream": False,
    }


@pytest.fixture
def enforcement_lab(monkeypatch):
    events = []
    provider_calls = []
    opa_inputs = []

    state = {
        "handler": lambda request: httpx.Response(
            200,
            json={
                "result": {
                    "allow": True,
                    "reason": "ALLOW",
                }
            },
        )
    }

    def opa_handler(request):
        events.append("opa")
        opa_inputs.append(json.loads(request.content)["input"])
        return state["handler"](request)

    def provider_handler(request):
        events.append("provider")
        provider_calls.append(request)

        forwarded = json.loads(request.content)

        return httpx.Response(
            200,
            json={
                "id": "chatcmpl-day18",
                "object": "chat.completion",
                "created": 1700000000,
                "model": forwarded["model"],
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": "Approved mock response",
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
        "opa_inputs": opa_inputs,
        "state": state,
    }


# 1. An approved request must evaluate OPA before inference.
def test_allowed_request_evaluates_opa_first(enforcement_lab):
    lab = enforcement_lab

    response = client.post(
        "/v1/chat/completions",
        json=payload(),
        headers={"X-Application-ID": "finance-assistant"},
    )

    assert response.status_code == 200
    assert lab["events"] == ["opa", "provider"]
    assert len(lab["provider_calls"]) == 1

    # The spoofed header must not control the OPA identity.
    assert lab["opa_inputs"] == [
        {
            "application_id": "test-app",
            "model_id": "local-small",
        }
    ]


# 2. Explicit OPA denial blocks inference.
def test_opa_denial_blocks_provider(enforcement_lab):
    lab = enforcement_lab

    lab["state"]["handler"] = lambda request: httpx.Response(
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
    assert lab["events"] == ["opa"]
    assert lab["provider_calls"] == []


# 3. OPA's unknown-model decision returns 404.
def test_unknown_model_blocks_provider(enforcement_lab):
    lab = enforcement_lab

    lab["state"]["handler"] = lambda request: httpx.Response(
        200,
        json={
            "result": {
                "allow": False,
                "reason": "MODEL_NOT_REGISTERED",
            }
        },
    )

    response = client.post(
        "/v1/chat/completions",
        json=payload("unregistered-model"),
    )

    assert response.status_code == 404
    assert lab["provider_calls"] == []


# 4. Policy evaluation timeout must fail closed.
def test_opa_timeout_blocks_provider(enforcement_lab):
    lab = enforcement_lab

    def timeout(request):
        raise httpx.ReadTimeout(
            "Simulated OPA timeout",
            request=request,
        )

    lab["state"]["handler"] = timeout

    response = client.post(
        "/v1/chat/completions",
        json=payload(),
    )

    assert response.status_code == 503
    assert response.json()["detail"] == ("Policy evaluation unavailable.")
    assert lab["provider_calls"] == []


# 5. An OPA HTTP 503 must not allow fallback.
def test_opa_service_failure_blocks_provider(enforcement_lab):
    lab = enforcement_lab

    lab["state"]["handler"] = lambda request: httpx.Response(
        503,
        json={"error": "OPA unavailable"},
    )

    response = client.post(
        "/v1/chat/completions",
        json=payload(),
    )

    assert response.status_code == 503
    assert lab["provider_calls"] == []


# 6. Malformed authorization results must fail closed.
def test_invalid_opa_decision_blocks_provider(enforcement_lab):
    lab = enforcement_lab

    lab["state"]["handler"] = lambda request: httpx.Response(
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
    assert lab["provider_calls"] == []


# 7. HTTP 200 without a decision must fail closed.
def test_missing_opa_result_blocks_provider(enforcement_lab):
    lab = enforcement_lab

    lab["state"]["handler"] = lambda request: httpx.Response(
        200,
        json={},
    )

    response = client.post(
        "/v1/chat/completions",
        json=payload(),
    )

    assert response.status_code == 503
    assert lab["provider_calls"] == []


# 8. OPA approval cannot invent an unregistered route.
def test_opa_allow_cannot_override_route_registry(
    enforcement_lab,
):
    lab = enforcement_lab

    response = client.post(
        "/v1/chat/completions",
        json=payload("unregistered-model"),
    )

    assert response.status_code == 503
    assert lab["events"] == ["opa"]
    assert lab["provider_calls"] == []
