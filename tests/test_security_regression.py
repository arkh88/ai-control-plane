"""Security regression tests for gateway access controls."""

import hashlib
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app.auth import require_application
from app.main import app
from app.provider_client import get_provider_client

client = TestClient(app)

TEST_KEY = "day14-test-credential-only"


def key_digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def auth_headers(key: str = TEST_KEY) -> dict[str, str]:
    return {"Authorization": f"Bearer {key}"}


def payload(model: str = "local-small") -> dict:
    return {
        "model": model,
        "messages": [{"role": "user", "content": "Security test"}],
        "stream": False,
    }


@pytest.fixture
def security_lab(monkeypatch):
    """Use real authentication and a recording mock provider."""

    # The global conftest fixture normally skips authentication
    # for other API tests. Remove that override for this test.
    monkeypatch.delitem(
        app.dependency_overrides,
        require_application,
        raising=False,
    )

    monkeypatch.setenv(
        "AICP_API_KEY_SHA256",
        key_digest(TEST_KEY),
    )
    monkeypatch.setenv("AICP_APP_ID", "demo-app")

    provider_calls = []

    def handler(request):
        provider_calls.append(request)

        forwarded = json.loads(request.content)

        return httpx.Response(
            200,
            json={
                "id": "chatcmpl-security-test",
                "object": "chat.completion",
                "created": 1700000000,
                "model": forwarded["model"],
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": "Security test response",
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": None,
            },
        )

    async def override_provider_client():
        transport = httpx.MockTransport(handler)

        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://mock-provider:8001",
            timeout=5.0,
            trust_env=False,
        ) as provider:
            yield provider

    monkeypatch.setitem(
        app.dependency_overrides,
        get_provider_client,
        override_provider_client,
    )

    return provider_calls


# 1. Positive control: authentication and routing succeed.
def test_valid_key_forwards_once(security_lab):
    response = client.post(
        "/v1/chat/completions",
        json=payload(),
        headers=auth_headers(),
    )

    assert response.status_code == 200
    assert len(security_lab) == 1


# 2. Missing credentials must not reach inference.
def test_missing_key_never_reaches_provider(security_lab):
    response = client.post(
        "/v1/chat/completions",
        json=payload(),
    )

    assert response.status_code == 401
    assert security_lab == []


# 3. Invalid credentials must not reach inference.
def test_wrong_key_never_reaches_provider(security_lab):
    response = client.post(
        "/v1/chat/completions",
        json=payload(),
        headers=auth_headers("invalid-key"),
    )

    assert response.status_code == 401
    assert security_lab == []


# 4. Unsupported authentication schemes are rejected.
def test_basic_auth_cannot_bypass_bearer(security_lab):
    response = client.post(
        "/v1/chat/completions",
        json=payload(),
        headers={"Authorization": f"Basic {TEST_KEY}"},
    )

    assert response.status_code == 401
    assert security_lab == []


# 5. Missing trusted configuration must fail closed.
def test_missing_auth_config_fails_closed(security_lab, monkeypatch):
    monkeypatch.delenv(
        "AICP_API_KEY_SHA256",
        raising=False,
    )

    response = client.post(
        "/v1/chat/completions",
        json=payload(),
        headers=auth_headers(),
    )

    assert response.status_code == 503
    assert security_lab == []


# 6. A previous key stops working after configured rotation.
def test_old_key_rejected_after_rotation(security_lab, monkeypatch):
    monkeypatch.setenv(
        "AICP_API_KEY_SHA256",
        key_digest("replacement-test-key"),
    )

    response = client.post(
        "/v1/chat/completions",
        json=payload(),
        headers=auth_headers(),
    )

    assert response.status_code == 401
    assert security_lab == []


# 7. A valid key with no model permissions is denied.
def test_unknown_application_denied(security_lab, monkeypatch):
    monkeypatch.setenv(
        "AICP_APP_ID",
        "unregistered-app",
    )

    response = client.post(
        "/v1/chat/completions",
        json=payload(),
        headers=auth_headers(),
    )

    assert response.status_code == 403
    assert security_lab == []


# 8. A caller cannot impersonate another application.
def test_spoofed_identity_cannot_access_restricted_model(
    security_lab,
):
    response = client.post(
        "/v1/chat/completions",
        json=payload("restricted-small"),
        headers={
            **auth_headers(),
            "X-Application-ID": "finance-assistant",
        },
    )

    assert response.status_code == 403
    assert security_lab == []
