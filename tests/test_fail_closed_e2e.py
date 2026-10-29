"""End-to-end fail-closed security acceptance tests."""

import hashlib
import json
import sqlite3
from contextlib import closing
from uuid import UUID

import httpx
import pytest
from fastapi.testclient import TestClient

from app.auth import require_application
from app.evidence import (
    EvidenceStore,
    EvidenceStoreError,
    get_evidence_store,
)
from app.main import app
from app.policy_client import get_policy_client
from app.provider_client import get_provider_client

client = TestClient(app)
TEST_KEY = "day21-local-test-key"


def headers():
    return {"Authorization": f"Bearer {TEST_KEY}"}


def payload(model="local-small"):
    return {
        "model": model,
        "messages": [{"role": "user", "content": "Day 21 verification"}],
        "stream": False,
    }


def evidence_rows(db_path):
    """Read only records committed to a separate connection."""

    if not db_path.exists():
        return []

    with closing(sqlite3.connect(db_path)) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            "SELECT * FROM policy_evidence ORDER BY rowid"
        ).fetchall()

        return [dict(row) for row in rows]


@pytest.fixture
def security_lab(monkeypatch, tmp_path):
    """Trace OPA, evidence commits, and provider invocations."""

    db_path = tmp_path / "evidence.sqlite3"
    events = []
    provider_calls = []

    state = {
        "opa": "allow",
        "evidence": "ok",
        "provider": "ok",
    }

    # Exercise actual API-key authentication, not the
    # shortcut used by most of our older gateway tests.
    monkeypatch.delitem(
        app.dependency_overrides,
        require_application,
        raising=False,
    )

    monkeypatch.setenv(
        "AICP_API_KEY_SHA256",
        hashlib.sha256(TEST_KEY.encode()).hexdigest(),
    )
    monkeypatch.setenv("AICP_APP_ID", "demo-app")

    class TracedEvidenceStore(EvidenceStore):
        def write(self, record):
            events.append("evidence_attempt")

            if state["evidence"] == "fail":
                raise EvidenceStoreError("Simulated evidence commit failure")

            super().write(record)
            events.append("evidence_committed")

    def opa_handler(request):
        events.append("opa")
        mode = state["opa"]

        if mode == "timeout":
            raise httpx.ReadTimeout(
                "Simulated OPA timeout",
                request=request,
            )

        if mode == "malformed":
            return httpx.Response(
                200,
                json={
                    "result": {
                        "allow": "true",
                        "reason": "ALLOW",
                    }
                },
            )

        if mode == "deny":
            decision = {
                "allow": False,
                "reason": "MODEL_NOT_ALLOWED",
            }
        elif mode == "unknown_model":
            decision = {
                "allow": False,
                "reason": "MODEL_NOT_REGISTERED",
            }
        else:
            decision = {
                "allow": True,
                "reason": "ALLOW",
            }

        return httpx.Response(
            200,
            json={"result": decision},
        )

    def provider_handler(request):
        # This assertion runs before the mock provider
        # processes the request.
        assert "evidence_committed" in events

        rows = evidence_rows(db_path)
        assert rows
        assert rows[-1]["outcome"] == "allow"

        events.append("provider")
        provider_calls.append(request)

        if state["provider"] == "timeout":
            raise httpx.ReadTimeout(
                "Simulated provider timeout",
                request=request,
            )

        if state["provider"] == "http_error":
            return httpx.Response(
                503,
                json={"detail": "Provider unavailable"},
            )

        forwarded = json.loads(request.content)

        return httpx.Response(
            200,
            json={
                "id": "chatcmpl-day21",
                "object": "chat.completion",
                "created": 1700000000,
                "model": forwarded["model"],
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

    monkeypatch.setitem(
        app.dependency_overrides,
        get_evidence_store,
        lambda: TracedEvidenceStore(str(db_path)),
    )

    return {
        "db_path": db_path,
        "events": events,
        "calls": provider_calls,
        "state": state,
    }


# 1. Happy path: all controls succeed in the right order.
def test_approved_request_commits_before_inference(security_lab):
    lab = security_lab

    response = client.post(
        "/v1/chat/completions",
        json=payload(),
        headers=headers(),
    )

    assert response.status_code == 200
    assert lab["events"] == [
        "opa",
        "evidence_attempt",
        "evidence_committed",
        "provider",
    ]
    assert len(lab["calls"]) == 1

    record = evidence_rows(lab["db_path"])[0]

    assert record["outcome"] == "allow"
    assert record["reason"] == "ALLOW"
    assert record["application_id"] == "demo-app"
    assert record["model_id"] == "local-small"
    assert record["request_id"] == response.headers["X-Request-ID"]
    assert UUID(record["evidence_id"]).version == 4


# 2. No credentials: never evaluate policy or infer.
def test_missing_auth_blocks_everything(security_lab):
    lab = security_lab

    response = client.post(
        "/v1/chat/completions",
        json=payload(),
    )

    assert response.status_code == 401
    assert lab["events"] == []
    assert lab["calls"] == []
    assert evidence_rows(lab["db_path"]) == []


# 3. OPA denial is recorded, and inference is blocked.
def test_policy_denial_blocks_inference(security_lab):
    lab = security_lab
    lab["state"]["opa"] = "deny"

    response = client.post(
        "/v1/chat/completions",
        json=payload("restricted-small"),
        headers=headers(),
    )

    assert response.status_code == 403
    assert lab["events"] == [
        "opa",
        "evidence_attempt",
        "evidence_committed",
    ]
    assert lab["calls"] == []

    record = evidence_rows(lab["db_path"])[0]
    assert record["outcome"] == "deny"
    assert record["reason"] == "MODEL_NOT_ALLOWED"


# 4. Unknown model is denied before inference.
def test_unknown_model_blocks_inference(security_lab):
    lab = security_lab
    lab["state"]["opa"] = "unknown_model"

    response = client.post(
        "/v1/chat/completions",
        json=payload("unknown-model"),
        headers=headers(),
    )

    assert response.status_code == 404
    assert lab["calls"] == []

    record = evidence_rows(lab["db_path"])[0]
    assert record["outcome"] == "deny"
    assert record["reason"] == "MODEL_NOT_REGISTERED"


# 5. OPA timeout fails closed and records an error.
def test_opa_timeout_blocks_inference(security_lab):
    lab = security_lab
    lab["state"]["opa"] = "timeout"

    response = client.post(
        "/v1/chat/completions",
        json=payload(),
        headers=headers(),
    )

    assert response.status_code == 503
    assert lab["calls"] == []

    record = evidence_rows(lab["db_path"])[0]
    assert record["outcome"] == "error"
    assert record["reason"] == "POLICY_EVALUATION_ERROR"


# 6. Malformed OPA response cannot grant access.
def test_malformed_policy_decision_fails_closed(security_lab):
    lab = security_lab
    lab["state"]["opa"] = "malformed"

    response = client.post(
        "/v1/chat/completions",
        json=payload(),
        headers=headers(),
    )

    assert response.status_code == 503
    assert lab["calls"] == []

    record = evidence_rows(lab["db_path"])[0]
    assert record["outcome"] == "error"
    assert record["reason"] == "POLICY_EVALUATION_ERROR"


# 7. OPA cannot authorize an unregistered provider route.
def test_approved_but_unknown_route_blocks_inference(
    security_lab,
):
    lab = security_lab

    # Mock OPA allows, but the trusted route registry does not.
    response = client.post(
        "/v1/chat/completions",
        json=payload("unknown-model"),
        headers=headers(),
    )

    assert response.status_code == 503
    assert lab["calls"] == []

    record = evidence_rows(lab["db_path"])[0]
    assert record["outcome"] == "error"
    assert record["reason"] == "ROUTE_UNAVAILABLE"


# 8. The essential fail-closed evidence test.
def test_evidence_commit_failure_blocks_inference(
    security_lab,
):
    lab = security_lab
    lab["state"]["evidence"] = "fail"

    response = client.post(
        "/v1/chat/completions",
        json=payload(),
        headers=headers(),
    )

    assert response.status_code == 503
    assert response.json()["detail"] == ("Governance evidence unavailable.")

    assert lab["events"] == [
        "opa",
        "evidence_attempt",
    ]
    assert lab["calls"] == []
    assert evidence_rows(lab["db_path"]) == []


# 9. A provider HTTP error happens after evidence commit.
def test_provider_failure_preserves_allow_evidence(
    security_lab,
):
    lab = security_lab
    lab["state"]["provider"] = "http_error"

    response = client.post(
        "/v1/chat/completions",
        json=payload(),
        headers=headers(),
    )

    assert response.status_code == 502
    assert lab["events"] == [
        "opa",
        "evidence_attempt",
        "evidence_committed",
        "provider",
    ]

    assert len(lab["calls"]) == 1
    assert evidence_rows(lab["db_path"])[0]["outcome"] == "allow"


# 10. Provider timeout also happens after evidence commit.
def test_provider_timeout_preserves_allow_evidence(
    security_lab,
):
    lab = security_lab
    lab["state"]["provider"] = "timeout"

    response = client.post(
        "/v1/chat/completions",
        json=payload(),
        headers=headers(),
    )

    assert response.status_code == 504
    assert lab["events"] == [
        "opa",
        "evidence_attempt",
        "evidence_committed",
        "provider",
    ]

    assert len(lab["calls"]) == 1
    assert evidence_rows(lab["db_path"])[0]["outcome"] == "allow"
