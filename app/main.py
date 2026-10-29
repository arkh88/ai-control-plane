import logging
from typing import Annotated
from uuid import uuid4

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel, ValidationError

from app.auth import ApplicationIdentity, require_application
from app.evidence import (
    EvidenceRecord,
    EvidenceStore,
    EvidenceStoreError,
    get_evidence_store,
)
from app.model_registry import MODEL_REGISTRY
from app.policy_audit import PolicyOutcome, log_policy_event
from app.policy_client import (
    PolicyClientError,
    evaluate_model_access,
    get_policy_client,
)
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


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    """Generate one trusted correlation ID per HTTP request."""

    request_id = str(uuid4())
    request.state.request_id = request_id

    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id

    return response


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
    http_request: Request,
    identity: Annotated[
        ApplicationIdentity,
        Depends(require_application),
    ],
    client: Annotated[
        httpx.AsyncClient,
        Depends(get_provider_client),
    ],
    policy_client: Annotated[
        httpx.AsyncClient,
        Depends(get_policy_client),
    ],
    evidence_store: Annotated[
        EvidenceStore,
        Depends(get_evidence_store),
    ],
) -> ChatCompletionResponse:
    """Authenticate, authorize, log, and forward inference."""

    request_id = http_request.state.request_id

    def record_decision(
        outcome: PolicyOutcome,
        reason: str,
    ) -> None:
        """Commit evidence before emitting its operational log."""

        record = EvidenceRecord(
            request_id=request_id,
            application_id=identity.application_id,
            model_id=request.model,
            outcome=outcome,
            reason=reason,
        )

        try:
            evidence_store.write(record)
        except EvidenceStoreError as exc:
            raise HTTPException(
                status_code=503,
                detail="Governance evidence unavailable.",
            ) from exc

        log_policy_event(
            request_id=request_id,
            application_id=identity.application_id,
            model_id=request.model,
            outcome=outcome,
            reason=reason,
        )

    # Step 1: Evaluate authorization with OPA.
    try:
        decision = await evaluate_model_access(
            client=policy_client,
            application_id=identity.application_id,
            model_id=request.model,
        )

    except PolicyClientError as exc:
        record_decision(
            "error",
            "POLICY_EVALUATION_ERROR",
        )

        raise HTTPException(
            status_code=503,
            detail="Policy evaluation unavailable.",
        ) from exc

    # Step 2: Reject explicit OPA denials.
    if not decision.allow:
        record_decision(
            "deny",
            decision.reason,
        )
        if decision.reason == "MODEL_NOT_REGISTERED":
            raise HTTPException(
                status_code=404,
                detail="Model not found.",
            )

        raise HTTPException(
            status_code=403,
            detail="Application is not authorized for this model.",
        )

    # Step 3: Verify the approved provider route.
    registration = MODEL_REGISTRY.get(request.model)

    if registration is None or registration.provider_id != "mock-provider":
        record_decision(
            "error",
            "ROUTE_UNAVAILABLE",
        )

        raise HTTPException(
            status_code=503,
            detail="Approved model route unavailable.",
        )

    # Step 4: Log the successful authorization.
    record_decision(
        "allow",
        decision.reason,
    )

    # Step 5: Forward to the approved model provider.
    try:
        response = await client.post(
            "/v1/chat/completions",
            json=request.model_dump(),
        )

        response.raise_for_status()

        return ChatCompletionResponse.model_validate(response.json())

    except httpx.TimeoutException as exc:
        raise HTTPException(
            status_code=504,
            detail="Model provider timed out.",
        ) from exc

    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail="Model provider unavailable.",
        ) from exc

    except (ValueError, ValidationError) as exc:
        raise HTTPException(
            status_code=502,
            detail="Invalid model provider response.",
        ) from exc
