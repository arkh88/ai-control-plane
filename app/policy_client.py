"""Typed, fail-closed HTTP client for Open Policy Agent."""

import os
from collections.abc import AsyncIterator
from typing import Literal

import httpx
from pydantic import (
    BaseModel,
    ConfigDict,
    StrictBool,
    ValidationError,
    model_validator,
)

OPA_DECISION_PATH = "/v1/data/aicp/authz/decision"

DecisionReason = Literal[
    "ALLOW",
    "MODEL_NOT_ALLOWED",
    "UNKNOWN_APPLICATION",
    "MODEL_NOT_REGISTERED",
]


class PolicyClientError(Exception):
    """Policy evaluation could not produce a trusted decision."""


class PolicyDecision(BaseModel):
    """Strict authorization decision returned by OPA."""

    model_config = ConfigDict(extra="forbid")

    allow: StrictBool
    reason: DecisionReason

    @model_validator(mode="after")
    def validate_consistency(self):
        if self.allow and self.reason != "ALLOW":
            raise ValueError("Allowed decision has an invalid reason.")

        if not self.allow and self.reason == "ALLOW":
            raise ValueError("Denied decision has an invalid reason.")

        return self


class OPAResponse(BaseModel):
    """OPA Data API response envelope."""

    result: PolicyDecision


async def get_policy_client() -> AsyncIterator[httpx.AsyncClient]:
    """Create an HTTP client with a trusted OPA base URL."""

    opa_url = os.getenv("OPA_URL", "http://opa:8181")

    async with httpx.AsyncClient(
        base_url=opa_url,
        timeout=httpx.Timeout(2.0),
        follow_redirects=False,
        trust_env=False,
    ) as client:
        yield client


async def evaluate_model_access(
    client: httpx.AsyncClient,
    application_id: str,
    model_id: str,
) -> PolicyDecision:
    """Evaluate access; never invent an allow decision."""

    try:
        response = await client.post(
            OPA_DECISION_PATH,
            json={
                "input": {
                    "application_id": application_id,
                    "model_id": model_id,
                }
            },
        )

        response.raise_for_status()

        parsed = OPAResponse.model_validate(response.json())

        return parsed.result

    except httpx.TimeoutException as exc:
        raise PolicyClientError("OPA policy evaluation timed out.") from exc

    except httpx.HTTPError as exc:
        raise PolicyClientError("OPA policy service unavailable.") from exc

    except (ValueError, ValidationError) as exc:
        raise PolicyClientError("OPA returned an invalid policy decision.") from exc
