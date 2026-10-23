from fastapi import FastAPI
from pydantic import BaseModel


app = FastAPI(
    title="AI Control Plane",
    description=(
        "Open-source AI governance and "
        "runtime security platform."
    ),
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