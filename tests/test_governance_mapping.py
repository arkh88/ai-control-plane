"""Tests for policy-version and governance-control evidence."""

import asyncio
import json
import sqlite3
from contextlib import closing

import httpx
import pytest
from fastapi.testclient import TestClient

from app.evidence import (
    EvidenceRecord,
    EvidenceStore,
    EvidenceStoreError,
    get_evidence_store,
)
from app.governance_controls import controls_for_reason
from app.main import app
from app.policy_client import (
    PolicyClientError,
    evaluate_model_access,
    get_policy_client,
)

client = TestClient(app)


def read_rows(path):
    with closing(sqlite3.connect(path)) as db:
        db.row_factory = sqlite3.Row
        return [
            dict(row)
            for row in db.execute("SELECT * FROM policy_evidence ORDER BY rowid")
        ]


def record(request_id, reason="ALLOW", version="model-access/v1"):
    return EvidenceRecord(
        request_id=request_id,
        application_id="test-app",
        model_id="local-small",
        outcome="allow" if reason == "ALLOW" else "deny",
        reason=reason,
        policy_version=version,
    )


# Tests 1-3: control mappings are explicit.
@pytest.mark.parametrize(
    ("reason", "expected"),
    [
        ("ALLOW", "AICP-AC-001"),
        ("MODEL_NOT_ALLOWED", "AICP-AC-001"),
        ("POLICY_EVALUATION_ERROR", "AICP-FC-001"),
    ],
)
def test_control_mapping(reason, expected):
    assert expected in controls_for_reason(reason)


# Test 4: unmapped reasons cannot be silently stored.
def test_unmapped_reason_fails_closed(tmp_path):
    store = EvidenceStore(str(tmp_path / "evidence.db"))

    with pytest.raises(EvidenceStoreError):
        store.write(record("request-invalid", "UNKNOWN_REASON"))


# Test 5: new databases contain versioned control metadata.
def test_new_database_persists_governance_metadata(tmp_path):
    path = tmp_path / "evidence.db"
    EvidenceStore(str(path)).write(record("request-new"))

    rows = read_rows(path)

    assert len(rows) == 1
    assert rows[0]["policy_version"] == "model-access/v1"
    assert json.loads(rows[0]["control_ids"]) == [
        "AICP-AC-001",
        "AICP-EV-001",
    ]


# Test 6: an existing Day 20 database is preserved.
def test_existing_database_migrates_without_relabeling(tmp_path):
    path = tmp_path / "legacy.db"

    with sqlite3.connect(path) as db:
        db.execute(
            """
            CREATE TABLE policy_evidence (
                evidence_id TEXT PRIMARY KEY NOT NULL,
                request_id TEXT NOT NULL UNIQUE,
                occurred_at TEXT NOT NULL,
                application_id TEXT NOT NULL,
                model_id TEXT NOT NULL,
                outcome TEXT NOT NULL,
                reason TEXT NOT NULL,
                policy_ref TEXT NOT NULL
            )
            """
        )
        db.execute(
            """
            INSERT INTO policy_evidence
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "legacy-evidence-id",
                "legacy-request-id",
                "2026-10-20T12:00:00+00:00",
                "test-app",
                "local-small",
                "allow",
                "ALLOW",
                "aicp.authz.decision",
            ),
        )

    EvidenceStore(str(path)).write(record("request-after-upgrade"))

    rows = read_rows(path)

    assert len(rows) == 2

    assert rows[0]["request_id"] == "legacy-request-id"
    assert rows[0]["policy_version"] == "not_reported"
    assert json.loads(rows[0]["control_ids"]) == []

    assert rows[1]["policy_version"] == "model-access/v1"
    assert "AICP-AC-001" in json.loads(rows[1]["control_ids"])


# Test 7: real gateway enforcement persists OPA's version.
def test_gateway_persists_reported_opa_version(tmp_path, monkeypatch):
    path = tmp_path / "gateway-evidence.db"

    def handler(request):
        return httpx.Response(
            200,
            json={
                "result": {
                    "allow": True,
                    "reason": "ALLOW",
                    "policy_version": "model-access/v1",
                }
            },
        )

    async def override_policy_client():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            base_url="http://opa:8181",
            trust_env=False,
        ) as opa:
            yield opa

    monkeypatch.setitem(
        app.dependency_overrides,
        get_policy_client,
        override_policy_client,
    )
    monkeypatch.setitem(
        app.dependency_overrides,
        get_evidence_store,
        lambda: EvidenceStore(str(path)),
    )

    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "local-small",
            "messages": [{"role": "user", "content": "Version test"}],
            "stream": False,
        },
    )

    assert response.status_code == 200

    rows = read_rows(path)
    assert len(rows) == 1
    assert rows[0]["request_id"] == response.headers["X-Request-ID"]
    assert rows[0]["policy_version"] == "model-access/v1"
    assert "AICP-AC-001" in json.loads(rows[0]["control_ids"])


# Test 8: unexpected policy versions are rejected by the client.
def test_unexpected_policy_version_is_rejected():
    async def run():
        def handler(request):
            return httpx.Response(
                200,
                json={
                    "result": {
                        "allow": True,
                        "reason": "ALLOW",
                        "policy_version": "model-access/v999",
                    }
                },
            )

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            base_url="http://opa:8181",
        ) as opa:
            await evaluate_model_access(
                client=opa,
                application_id="demo-app",
                model_id="local-small",
            )

    with pytest.raises(
        PolicyClientError,
        match="invalid policy decision",
    ):
        asyncio.run(run())
