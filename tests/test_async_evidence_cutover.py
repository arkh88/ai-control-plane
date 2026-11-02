"""Day 29: asynchronous evidence gateway security tests."""

import asyncio

import httpx
import pytest
from fastapi.testclient import TestClient

from app.evidence import (
    EvidenceStoreError,
    get_evidence_store,
)
from app.main import app
from app.policy_client import get_policy_client
from app.provider_client import get_provider_client

client = TestClient(app)


def payload(model="local-small"):
    return {
        "model": model,
        "messages": [{"role": "user", "content": "Day 29 async test"}],
        "stream": False,
    }


@pytest.fixture
def async_lab(monkeypatch):
    events = []
    saved = []
    provider_calls = []

    state = {
        "opa": "allow",
        "storage": "ok",
        "provider": "ok",
    }

    class FakeAsyncStore:
        async def write(self, record):
            events.append("evidence_attempt")

            # Exercise the asynchronous execution path.
            await asyncio.sleep(0)

            if state["storage"] == "fail":
                raise EvidenceStoreError("Simulated database failure")

            saved.append(record)
            events.append("evidence_committed")

    def opa_handler(request):
        events.append("opa")

        if state["opa"] == "timeout":
            raise httpx.ReadTimeout(
                "Simulated OPA timeout",
                request=request,
            )

        reason = {
            "allow": "ALLOW",
            "deny": "MODEL_NOT_ALLOWED",
            "unknown": "MODEL_NOT_REGISTERED",
        }[state["opa"]]

        return httpx.Response(
            200,
            json={
                "result": {
                    "allow": reason == "ALLOW",
                    "reason": reason,
                    "policy_version": "model-access/v1",
                }
            },
        )

    def provider_handler(request):
        # The gateway may not reach this handler
        # until evidence persistence completes.
        assert events[-1] == "evidence_committed"
        assert saved[-1].outcome == "allow"

        events.append("provider")
        provider_calls.append(request)

        if state["provider"] == "fail":
            return httpx.Response(
                503,
                json={"detail": "Provider unavailable"},
            )

        return httpx.Response(
            200,
            json={
                "id": "chatcmpl-day29",
                "object": "chat.completion",
                "created": 1700000000,
                "model": "local-small",
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": "Approved response",
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": None,
            },
        )

    async def override_opa():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(opa_handler),
            base_url="http://opa:8181",
            trust_env=False,
        ) as opa:
            yield opa

    async def override_provider():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(provider_handler),
            base_url="http://mock-provider:8001",
            trust_env=False,
        ) as provider:
            yield provider

    monkeypatch.setitem(
        app.dependency_overrides,
        get_evidence_store,
        lambda: FakeAsyncStore(),
    )
    monkeypatch.setitem(
        app.dependency_overrides,
        get_policy_client,
        override_opa,
    )
    monkeypatch.setitem(
        app.dependency_overrides,
        get_provider_client,
        override_provider,
    )

    return {
        "events": events,
        "saved": saved,
        "calls": provider_calls,
        "state": state,
    }


def test_allow_waits_for_evidence_commit(async_lab):
    response = client.post(
        "/v1/chat/completions",
        json=payload(),
    )

    assert response.status_code == 200
    assert async_lab["events"] == [
        "opa",
        "evidence_attempt",
        "evidence_committed",
        "provider",
    ]

    assert len(async_lab["saved"]) == 1
    assert async_lab["saved"][0].request_id == (response.headers["X-Request-ID"])


def test_denial_is_saved_without_provider(async_lab):
    async_lab["state"]["opa"] = "deny"

    response = client.post(
        "/v1/chat/completions",
        json=payload("restricted-small"),
    )

    assert response.status_code == 403
    assert async_lab["calls"] == []
    assert async_lab["saved"][0].outcome == "deny"


def test_unknown_model_is_auditable(async_lab):
    async_lab["state"]["opa"] = "unknown"

    response = client.post(
        "/v1/chat/completions",
        json=payload("unknown-model"),
    )

    assert response.status_code == 404
    assert async_lab["calls"] == []
    assert async_lab["saved"][0].reason == "MODEL_NOT_REGISTERED"


def test_opa_timeout_saves_error(async_lab):
    async_lab["state"]["opa"] = "timeout"

    response = client.post(
        "/v1/chat/completions",
        json=payload(),
    )

    assert response.status_code == 503
    assert async_lab["calls"] == []
    assert async_lab["saved"][0].outcome == "error"
    assert async_lab["saved"][0].reason == "POLICY_EVALUATION_ERROR"
    assert async_lab["saved"][0].policy_version == "not_reported"


def test_storage_failure_blocks_provider(async_lab):
    async_lab["state"]["storage"] = "fail"

    response = client.post(
        "/v1/chat/completions",
        json=payload(),
    )

    assert response.status_code == 503
    assert response.json()["detail"] == ("Governance evidence unavailable.")
    assert async_lab["calls"] == []
    assert async_lab["saved"] == []
    assert async_lab["events"] == [
        "opa",
        "evidence_attempt",
    ]


def test_provider_failure_preserves_committed_evidence(
    async_lab,
):
    async_lab["state"]["provider"] = "fail"

    response = client.post(
        "/v1/chat/completions",
        json=payload(),
    )

    assert response.status_code == 502
    assert len(async_lab["calls"]) == 1
    assert async_lab["saved"][0].outcome == "allow"


def test_unavailable_route_is_recorded(async_lab):
    # Mock OPA approves, but the trusted local model
    # registry does not contain this route.
    response = client.post(
        "/v1/chat/completions",
        json=payload("unknown-model"),
    )

    assert response.status_code == 503
    assert async_lab["calls"] == []
    assert async_lab["saved"][0].outcome == "error"
    assert async_lab["saved"][0].reason == "ROUTE_UNAVAILABLE"


@pytest.mark.parametrize(
    "backend",
    [None, "invalid-backend"],
)
def test_missing_or_invalid_backend_fails_closed(monkeypatch, backend):
    # Exercise the actual backend selector rather
    # than the test fixture's overridden dependency.
    monkeypatch.delitem(
        app.dependency_overrides,
        get_evidence_store,
        raising=False,
    )

    if backend is None:
        monkeypatch.delenv(
            "AICP_EVIDENCE_BACKEND",
            raising=False,
        )
    else:
        monkeypatch.setenv(
            "AICP_EVIDENCE_BACKEND",
            backend,
        )

    response = client.post(
        "/v1/chat/completions",
        json=payload(),
    )

    assert response.status_code == 503
    assert response.json()["detail"] == ("Governance evidence unavailable.")
