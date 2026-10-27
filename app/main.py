import logging
from typing import Annotated

import httpx
from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, ValidationError

from app.provider_client import get_provider_client
from app.schemas import (
    ChatCompletionRequest,
    ChatCompletionResponse,
)

logger = logging.getLogger(__name__)

app = FastAPI(
    title="AI Control Plane",
    description=("Open-source AI governance and runtime security platform."),
    version="0.1.0",
)


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


@app.get(
    "/health/live",
    response_model=HealthResponse,
    tags=["Health"],
)
async def health_live() -> HealthResponse:
    """Check whether the API process is running."""
    return HealthResponse(
        status="ok",
        service="ai-control-plane",
        version=app.version,
    )


@app.post(
    "/v1/chat/completions",
    response_model=ChatCompletionResponse,
    tags=["AI Inference"],
    responses={
        502: {"description": "Invalid or failed model provider response"},
        504: {"description": "Model provider timed out"},
    },
)
async def create_chat_completion(
    request: ChatCompletionRequest,
    client: Annotated[
        httpx.AsyncClient,
        Depends(get_provider_client),
    ],
) -> ChatCompletionResponse:
    """Forward a validated request to the configured mock provider."""

    try:
        response = await client.post(
            "/v1/chat/completions",
            json=request.model_dump(),
        )
        response.raise_for_status()

        # Validate the upstream response before returning it.
        return ChatCompletionResponse.model_validate(response.json())

    except httpx.TimeoutException as exc:
        raise HTTPException(
            status_code=504,
            detail="Model provider timed out.",
        ) from exc

    except httpx.HTTPError as exc:
        logger.exception("Provider HTTP request failed")
        raise HTTPException(
            status_code=502,
            detail="Model provider unavailable.",
        ) from exc

    except (ValueError, ValidationError) as exc:
        raise HTTPException(
            status_code=502,
            detail="Invalid model provider response.",
        ) from exc
