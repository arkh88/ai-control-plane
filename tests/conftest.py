"""Shared test fixtures for the AI Control Plane."""

import httpx
import pytest

from app.auth import ApplicationIdentity, require_application
from app.main import app as gateway_app
from app.mock_provider import app as mock_app
from app.provider_client import get_provider_client


@pytest.fixture(autouse=True)
def use_mock_provider():
    """Provide an in-memory model and test identity."""

    async def override_provider_client():
        transport = httpx.ASGITransport(app=mock_app)

        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://mock-provider:8001",
            timeout=5.0,
        ) as client:
            yield client

    def override_application():
        return ApplicationIdentity(application_id="test-app")

    original = gateway_app.dependency_overrides.copy()

    gateway_app.dependency_overrides[get_provider_client] = override_provider_client
    gateway_app.dependency_overrides[require_application] = override_application

    yield

    gateway_app.dependency_overrides.clear()
    gateway_app.dependency_overrides.update(original)
