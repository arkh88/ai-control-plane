"""Governance evidence persistence and enforcement tests."""

import json
import sqlite3
from contextlib import closing
from uuid import UUID

import httpx
import pytest
from fastapi.testclient import TestClient

from app.evidence import EvidenceStore, get_evidence_store
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


def read_evidence(path):
    """Read committed evidence through a new DB connection."""
    with closing(sqlite3.connect(path)) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            "SELECT * FROM policy_evidence ORDER BY rowid"
        ).fetchall()
        return [dict(row) for row in rows]


@pytest.fixture
def evidence_lab(tmp_path, monkeypatch):
    db_path = tmp_path / "evidence.sqlite3"
    provider_calls = []
    events = []

    state = {"opa_handler": None}

    def opa_handler(request):
        events.append("opa")

        if state["opa_handler"] is not None:
            return state["opa_handler"](request)

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
        # Verify evidence is already committed and readable
        # from a separate SQLite connection.
        assert len(read_evidence(db_path)) >= 1

        events.append("provider")
        provider_calls.append(request)

        forwarded = json.loads(request.content)

        return httpx.Response(
            200,
            json={
                "id": "chatcmpl-day20",
                "object": "chat.completion",
                "created": 1700000000,
                "model": forwarded["model"],
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": "Evidence-backed response",
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
        lambda: EvidenceStore(str(db_path)),
    )

    return {
        "path": db_path,
        "calls": provider_calls,
        "events": events,
        "state": state,
    }


# 1. Evidence is committed before provider execution.
def test_allow_committed_before_provider(evidence_lab):
    lab = evidence_lab

    response = client.post(
        "/v1/chat/completions",
        json=payload(),
    )

    assert response.status_code == 200
    assert lab["events"] == ["opa", "provider"]
    assert len(lab["calls"]) == 1

    rows = read_evidence(lab["path"])
    assert len(rows) == 1

    record = rows[0]
    assert UUID(record["evidence_id"]).version == 4
    assert record["request_id"] == response.headers["X-Request-ID"]
    assert record["application_id"] == "test-app"
    assert record["model_id"] == "local-small"
    assert record["outcome"] == "allow"
    assert record["reason"] == "ALLOW"
    assert record["policy_ref"] == "aicp.authz.decision"
    assert record["occurred_at"]


# 2. Explicit policy denials are persisted.
def test_deny_is_persisted_without_inference(evidence_lab):
    lab = evidence_lab

    lab["state"]["opa_handler"] = lambda request: httpx.Response(
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
    assert lab["calls"] == []
    assert lab["events"] == ["opa"]

    rows = read_evidence(lab["path"])
    assert len(rows) == 1
    assert rows[0]["outcome"] == "deny"
    assert rows[0]["reason"] == "MODEL_NOT_ALLOWED"


# 3. Unknown model denials retain their reason.
def test_unknown_model_evidence(evidence_lab):
    lab = evidence_lab

    lab["state"]["opa_handler"] = lambda request: httpx.Response(
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
        json=payload("unknown-model"),
    )

    assert response.status_code == 404
    assert lab["calls"] == []

    record = read_evidence(lab["path"])[0]
    assert record["outcome"] == "deny"
    assert record["reason"] == "MODEL_NOT_REGISTERED"


# 4. Policy evaluation failures are persisted.
def test_opa_timeout_evidence(evidence_lab):
    lab = evidence_lab

    def timeout(request):
        raise httpx.ReadTimeout(
            "Simulated OPA timeout",
            request=request,
        )

    lab["state"]["opa_handler"] = timeout

    response = client.post(
        "/v1/chat/completions",
        json=payload(),
    )

    assert response.status_code == 503
    assert lab["calls"] == []

    record = read_evidence(lab["path"])[0]
    assert record["outcome"] == "error"
    assert record["reason"] == "POLICY_EVALUATION_ERROR"


# 5. Malformed OPA decisions produce error evidence.
def test_invalid_opa_decision_evidence(evidence_lab):
    lab = evidence_lab

    lab["state"]["opa_handler"] = lambda request: httpx.Response(200, json={})

    response = client.post(
        "/v1/chat/completions",
        json=payload(),
    )

    assert response.status_code == 503
    assert lab["calls"] == []

    record = read_evidence(lab["path"])[0]
    assert record["outcome"] == "error"


# 6. OPA approval cannot bypass routing controls.
def test_route_failure_is_persisted(evidence_lab):
    lab = evidence_lab

    response = client.post(
        "/v1/chat/completions",
        json=payload("unknown-model"),
    )

    assert response.status_code == 503
    assert lab["calls"] == []

    record = read_evidence(lab["path"])[0]
    assert record["outcome"] == "error"
    assert record["reason"] == "ROUTE_UNAVAILABLE"


# 7. Missing evidence storage prevents inference.
def test_evidence_write_failure_blocks_inference(evidence_lab, tmp_path, monkeypatch):
    lab = evidence_lab

    # The parent directory deliberately does not exist.
    invalid_path = tmp_path / "missing-directory" / "evidence.db"

    monkeypatch.setitem(
        app.dependency_overrides,
        get_evidence_store,
        lambda: EvidenceStore(str(invalid_path)),
    )

    response = client.post(
        "/v1/chat/completions",
        json=payload(),
    )

    assert response.status_code == 503
    assert response.json()["detail"] == ("Governance evidence unavailable.")
    assert lab["events"] == ["opa"]
    assert lab["calls"] == []


# 8. Records are unique and exclude sensitive content.
def test_persistence_ids_and_data_minimization(evidence_lab):
    lab = evidence_lab
    secret = "DAY20_FAKE_API_SECRET"
    prompt = "DAY20_PRIVATE_PROMPT_CONTENT"

    responses = [
        client.post(
            "/v1/chat/completions",
            json=payload(content=prompt),
            headers={"Authorization": f"Bearer {secret}"},
        )
        for _ in range(2)
    ]

    assert all(r.status_code == 200 for r in responses)
    assert len(lab["calls"]) == 2

    rows = read_evidence(lab["path"])
    assert len(rows) == 2

    response_ids = {response.headers["X-Request-ID"] for response in responses}
    evidence_ids = {row["evidence_id"] for row in rows}
    stored_request_ids = {row["request_id"] for row in rows}

    assert len(response_ids) == 2
    assert len(evidence_ids) == 2
    assert stored_request_ids == response_ids

    serialized = json.dumps(rows)

    assert secret not in serialized
    assert prompt not in serialized
