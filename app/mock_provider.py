"""Deterministic mock AI provider for development and testing."""

from fastapi import FastAPI

from app.schemas import (
    AssistantMessage,
    ChatChoice,
    ChatCompletionRequest,
    ChatCompletionResponse,
)

app = FastAPI(
    title="AI Control Plane Mock Provider",
    version="0.1.0",
)

MOCK_CONTENT = "This is a deterministic mock response. No AI model was called."

# Fixed values make test responses reproducible.
MOCK_CREATED = 1_700_000_000
MOCK_COMPLETION_ID = "chatcmpl-mock-fixed"


@app.get("/health/live", tags=["Health"])
async def health_live() -> dict[str, str]:
    return {"status": "ok"}


@app.post(
    "/v1/chat/completions",
    response_model=ChatCompletionResponse,
    tags=["Mock Inference"],
)
async def create_mock_completion(
    request: ChatCompletionRequest,
) -> ChatCompletionResponse:
    """Return a predictable completion without running AI."""
    return ChatCompletionResponse(
        id=MOCK_COMPLETION_ID,
        created=MOCK_CREATED,
        model=request.model,
        choices=[
            ChatChoice(
                index=0,
                message=AssistantMessage(
                    content=MOCK_CONTENT,
                ),
                finish_reason="stop",
            )
        ],
        usage=None,
    )
