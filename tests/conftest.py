"""Shared pytest fixtures for gateway integration tests."""

import json

import httpx
import pytest

from app.auth import ApplicationIdentity, require_application
from app.evidence import EvidenceStore, get_evidence_store
from app.main import app as gateway_app
from app.mock_provider import app as mock_app
from app.model_registry import (
    APPLICATION_MODELS,
    MODEL_REGISTRY,
)
from app.policy_client import get_policy_client
from app.provider_client import get_provider_client


@pytest.fixture(autouse=True)
def use_mock_provider(tmp_path):
    """Keep gateway tests independent of Docker networking."""

    async def override_provider_client():
        transport = httpx.ASGITransport(app=mock_app)

        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://mock-provider:8001",
            trust_env=False,
        ) as client:
            yield client

    def override_application():
        return ApplicationIdentity(
            application_id="test-app",
        )

    def opa_handler(request):
        """Simulate our existing Rego allowlist in tests."""

        payload = json.loads(request.content)
        policy_input = payload["input"]

        app_id = policy_input.get("application_id")
        model_id = policy_input.get("model_id")

        if model_id not in MODEL_REGISTRY:
            reason = "MODEL_NOT_REGISTERED"
        elif app_id not in APPLICATION_MODELS:
            reason = "UNKNOWN_APPLICATION"
        elif model_id not in APPLICATION_MODELS[app_id]:
            reason = "MODEL_NOT_ALLOWED"
        else:
            reason = "ALLOW"

        return httpx.Response(
            200,
            json={
                "result": {
                    "allow": reason == "ALLOW",
                    "reason": reason,
                }
            },
        )

    async def override_policy_client():
        transport = httpx.MockTransport(opa_handler)

        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://opa:8181",
            trust_env=False,
        ) as client:
            yield client

    original = gateway_app.dependency_overrides.copy()

    gateway_app.dependency_overrides[get_provider_client] = override_provider_client
    gateway_app.dependency_overrides[get_policy_client] = override_policy_client
    gateway_app.dependency_overrides[require_application] = override_application

    def override_evidence_store():
        return EvidenceStore(str(tmp_path / "evidence.sqlite3"))

    gateway_app.dependency_overrides[get_evidence_store] = override_evidence_store
    yield

    gateway_app.dependency_overrides.clear()
    gateway_app.dependency_overrides.update(original)
