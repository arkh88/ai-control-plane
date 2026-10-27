"""HTTP client dependency for model provider requests."""

import os
from collections.abc import AsyncIterator

import httpx


async def get_provider_client() -> AsyncIterator[httpx.AsyncClient]:
    """Create a configured HTTP client for the mock provider."""

    # Trusted deployment configuration, never request input.
    base_url = os.environ.get(
        "MOCK_PROVIDER_URL",
        "http://mock-provider:8001",
    )

    async with httpx.AsyncClient(
        base_url=base_url,
        timeout=5.0,
        follow_redirects=False,
        trust_env=False,
    ) as client:
        yield client
