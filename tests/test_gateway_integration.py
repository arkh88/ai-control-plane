"""Integration tests for gateway/provider HTTP behavior."""

import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.provider_client import get_provider_client

client = TestClient(app)


def valid_payload() -> dict:
    return {
        "model": "local-small",
        "messages": [
            {
                "role": "user",
                "content": "Explain zero trust.",
            }
        ],
        "stream": False,
    }


def valid_provider_response() -> dict:
    return {
        "id": "chatcmpl-test-001",
        "object": "chat.completion",
        "created": 1700000000,
        "model": "local-small",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "Zero trust requires verification.",
                },
                "finish_reason": "stop",
            }
        ],
        "usage": None,
    }


@pytest.fixture
def install_transport(monkeypatch):
    """Install a test-only provider HTTP transport."""

    def install(handler):
        async def override_provider_client():
            transport = httpx.MockTransport(handler)

            async with httpx.AsyncClient(
                transport=transport,
                base_url="http://mock-provider:8001",
                timeout=5.0,
                trust_env=False,
            ) as provider_client:
                yield provider_client

        monkeypatch.setitem(
            app.dependency_overrides,
            get_provider_client,
            override_provider_client,
        )

    return install


def test_gateway_forwards_correct_payload(
    install_transport,
):
    received = []

    def handler(request):
        received.append(request)

        return httpx.Response(
            200,
            json=valid_provider_response(),
        )

    install_transport(handler)

    response = client.post(
        "/v1/chat/completions",
        json=valid_payload(),
    )

    assert response.status_code == 200
    assert len(received) == 1

    forwarded = received[0]

    assert forwarded.method == "POST"
    assert forwarded.url.path == "/v1/chat/completions"
    assert forwarded.url.host == "mock-provider"
    assert forwarded.headers["content-type"] == ("application/json")

    assert json.loads(forwarded.content) == valid_payload()
    assert response.json()["model"] == "local-small"


def test_invalid_request_is_not_forwarded(
    install_transport,
):
    provider_calls = []

    def handler(request):
        provider_calls.append(request)

        return httpx.Response(
            200,
            json=valid_provider_response(),
        )

    install_transport(handler)

    payload = valid_payload()
    payload["application_id"] = "fake-admin"

    response = client.post(
        "/v1/chat/completions",
        json=payload,
    )

    assert response.status_code == 422
    assert provider_calls == []


def test_malformed_provider_response(
    install_transport,
):
    def handler(request):
        return httpx.Response(
            200,
            json={
                "id": "broken",
                "unexpected": "schema",
            },
        )

    install_transport(handler)

    response = client.post(
        "/v1/chat/completions",
        json=valid_payload(),
    )

    assert response.status_code == 502
    assert response.json()["detail"] == ("Invalid model provider response.")


def test_invalid_provider_json(
    install_transport,
):
    def handler(request):
        return httpx.Response(
            200,
            content=b"this is not valid JSON",
            headers={"content-type": "application/json"},
        )

    install_transport(handler)

    response = client.post(
        "/v1/chat/completions",
        json=valid_payload(),
    )

    assert response.status_code == 502
    assert response.json()["detail"] == ("Invalid model provider response.")


def test_upstream_503_returns_gateway_502(
    install_transport,
):
    def handler(request):
        return httpx.Response(
            503,
            json={"detail": "Provider unavailable"},
        )

    install_transport(handler)

    response = client.post(
        "/v1/chat/completions",
        json=valid_payload(),
    )

    assert response.status_code == 502
    assert response.json()["detail"] == ("Model provider unavailable.")


def test_upstream_timeout_returns_504(
    install_transport,
):
    def handler(request):
        raise httpx.ReadTimeout(
            "Simulated provider timeout",
            request=request,
        )

    install_transport(handler)

    response = client.post(
        "/v1/chat/completions",
        json=valid_payload(),
    )

    assert response.status_code == 504
    assert response.json()["detail"] == ("Model provider timed out.")
