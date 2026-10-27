from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app.schemas import (
    ChatCompletionRequest,
    ChatCompletionResponse,
)

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
    responses={501: {"description": "Model inference is not yet implemented."}},
)
async def create_chat_completion(
    request: ChatCompletionRequest,
) -> ChatCompletionResponse:
    """Validate an AI request. Inference arrives on Day 9."""
    raise HTTPException(
        status_code=501,
        detail="AI inference is not implemented yet.",
    )
