"""Tests for registered model access and fixed routing."""

import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app.auth import ApplicationIdentity, require_application
from app.main import app
from app.provider_client import get_provider_client

client = TestClient(app)


def payload(model="local-small"):
    return {
        "model": model,
        "messages": [{"role": "user", "content": "Hello"}],
        "stream": False,
    }


@pytest.fixture
def provider_calls(use_mock_provider, monkeypatch):
    """Record calls to a fake provider without real networking."""
    calls = []

    def handler(request):
        calls.append(request)
        forwarded = json.loads(request.content)

        return httpx.Response(
            200,
            json={
                "id": "chatcmpl-model-test",
                "object": "chat.completion",
                "created": 1700000000,
                "model": forwarded["model"],
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": "Mock completion",
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": None,
            },
        )

    async def override_client():
        transport = httpx.MockTransport(handler)

        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://mock-provider:8001",
            trust_env=False,
        ) as provider:
            yield provider

    monkeypatch.setitem(
        app.dependency_overrides,
        get_provider_client,
        override_client,
    )

    return calls


def test_approved_model_is_forwarded(provider_calls):
    response = client.post(
        "/v1/chat/completions",
        json=payload("local-small"),
    )

    assert response.status_code == 200
    assert len(provider_calls) == 1
    assert provider_calls[0].url.host == "mock-provider"


def test_restricted_model_is_denied(provider_calls):
    response = client.post(
        "/v1/chat/completions",
        json=payload("restricted-small"),
    )

    assert response.status_code == 403
    assert provider_calls == []


def test_finance_app_can_use_restricted_model(provider_calls, monkeypatch):
    monkeypatch.setitem(
        app.dependency_overrides,
        require_application,
        lambda: ApplicationIdentity(application_id="finance-assistant"),
    )

    response = client.post(
        "/v1/chat/completions",
        json=payload("restricted-small"),
    )

    assert response.status_code == 200
    assert len(provider_calls) == 1
    assert response.json()["model"] == "restricted-small"


def test_unknown_model_is_rejected(provider_calls):
    response = client.post(
        "/v1/chat/completions",
        json=payload("unknown-model"),
    )

    assert response.status_code == 404
    assert provider_calls == []


def test_spoofed_identity_header_is_ignored(provider_calls):
    response = client.post(
        "/v1/chat/completions",
        json=payload("restricted-small"),
        headers={"X-Application-ID": "finance-assistant"},
    )

    assert response.status_code == 403
    assert provider_calls == []


def test_caller_cannot_override_provider_url(provider_calls):
    request_payload = payload()
    request_payload["provider_url"] = "http://untrusted-provider.example"

    response = client.post(
        "/v1/chat/completions",
        json=request_payload,
    )

    assert response.status_code == 422
    assert provider_calls == []
