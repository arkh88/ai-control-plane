"""Tests for gateway-to-provider failure handling."""

import httpx
from fastapi.testclient import TestClient

from app.main import app
from app.provider_client import get_provider_client

client = TestClient(app)

PAYLOAD = {
    "model": "local-small",
    "messages": [{"role": "user", "content": "Hello"}],
    "stream": False,
}


def set_fake_transport(handler):
    """Inject an HTTPX mock transport for one test."""

    async def override_client():
        transport = httpx.MockTransport(handler)

        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://mock-provider:8001",
        ) as provider_client:
            yield provider_client

    app.dependency_overrides[get_provider_client] = override_client


def test_provider_error_returns_502():
    def handler(request):
        return httpx.Response(503)

    set_fake_transport(handler)

    response = client.post(
        "/v1/chat/completions",
        json=PAYLOAD,
    )

    assert response.status_code == 502
    assert response.json()["detail"] == ("Model provider unavailable.")


def test_provider_timeout_returns_504():
    def handler(request):
        raise httpx.ReadTimeout(
            "Simulated timeout",
            request=request,
        )

    set_fake_transport(handler)

    response = client.post(
        "/v1/chat/completions",
        json=PAYLOAD,
    )

    assert response.status_code == 504


def test_invalid_provider_response_returns_502():
    def handler(request):
        return httpx.Response(
            200,
            json={"unexpected": "response"},
        )

    set_fake_transport(handler)

    response = client.post(
        "/v1/chat/completions",
        json=PAYLOAD,
    )

    assert response.status_code == 502
    assert response.json()["detail"] == ("Invalid model provider response.")
