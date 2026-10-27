"""Shared pytest fixtures."""

import httpx
import pytest

from app.main import app as gateway_app
from app.mock_provider import app as mock_app
from app.provider_client import get_provider_client


@pytest.fixture(autouse=True)
def use_mock_provider():
    """Route gateway requests to mock provider in memory."""

    async def override_provider_client():
        transport = httpx.ASGITransport(app=mock_app)

        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://mock-provider:8001",
            timeout=5.0,
        ) as client:
            yield client

    # Save the original override if one exists.
    original = gateway_app.dependency_overrides.get(get_provider_client)

    # Replace real networking with in-memory transport.
    gateway_app.dependency_overrides[get_provider_client] = override_provider_client

    yield

    # Restore the previous dependency configuration.
    if original is None:
        gateway_app.dependency_overrides.pop(get_provider_client, None)
    else:
        gateway_app.dependency_overrides[get_provider_client] = original
