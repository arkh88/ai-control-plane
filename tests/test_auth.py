"""Tests for application API-key authentication."""

import asyncio
import hashlib

import httpx
import pytest
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.testclient import TestClient

from app.auth import require_application
from app.main import app
from app.provider_client import get_provider_client

client = TestClient(app)

TEST_KEY = "test-key-for-pytest-only"


def payload():
    return {
        "model": "local-small",
        "messages": [{"role": "user", "content": "Hello"}],
        "stream": False,
    }


@pytest.fixture
def real_auth(use_mock_provider, monkeypatch):
    """Enable real authentication for these tests."""

    monkeypatch.delitem(
        app.dependency_overrides,
        require_application,
        raising=False,
    )

    monkeypatch.setenv(
        "AICP_API_KEY_SHA256",
        hashlib.sha256(TEST_KEY.encode()).hexdigest(),
    )
    monkeypatch.setenv(
        "AICP_APP_ID",
        "finance-assistant",
    )


def test_missing_key_returns_401(real_auth):
    response = client.post(
        "/v1/chat/completions",
        json=payload(),
    )

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_invalid_key_returns_401(real_auth):
    response = client.post(
        "/v1/chat/completions",
        json=payload(),
        headers={"Authorization": "Bearer wrong-key"},
    )

    assert response.status_code == 401


def test_valid_key_allows_inference(real_auth):
    response = client.post(
        "/v1/chat/completions",
        json=payload(),
        headers={"Authorization": f"Bearer {TEST_KEY}"},
    )

    assert response.status_code == 200
    assert response.json()["model"] == "local-small"


def test_wrong_authorization_scheme_returns_401(real_auth):
    response = client.post(
        "/v1/chat/completions",
        json=payload(),
        headers={"Authorization": f"Basic {TEST_KEY}"},
    )

    assert response.status_code == 401


def test_missing_auth_configuration_fails_closed(real_auth, monkeypatch):
    monkeypatch.delenv("AICP_API_KEY_SHA256")

    response = client.post(
        "/v1/chat/completions",
        json=payload(),
        headers={"Authorization": f"Bearer {TEST_KEY}"},
    )

    assert response.status_code == 503


def test_identity_comes_from_server_configuration(real_auth):
    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials=TEST_KEY,
    )

    identity = asyncio.run(require_application(credentials))

    assert identity.application_id == "finance-assistant"


def test_unauthenticated_request_never_reaches_provider(real_auth, monkeypatch):
    provider_calls = []

    def handler(request):
        provider_calls.append(request)
        return httpx.Response(200, json={})

    async def fake_provider_client():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            base_url="http://mock-provider:8001",
        ) as provider:
            yield provider

    monkeypatch.setitem(
        app.dependency_overrides,
        get_provider_client,
        fake_provider_client,
    )

    response = client.post(
        "/v1/chat/completions",
        json=payload(),
    )

    assert response.status_code == 401
    assert provider_calls == []
