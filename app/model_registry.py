"""Registered models and application access policy."""

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from fastapi import HTTPException


@dataclass(frozen=True, slots=True)
class ModelRegistration:
    model_id: str
    provider_id: str


# Trusted server-side model registry.
# Clients cannot supply provider destinations.
MODEL_REGISTRY: Mapping[str, ModelRegistration] = MappingProxyType(
    {
        "local-small": ModelRegistration(
            model_id="local-small",
            provider_id="mock-provider",
        ),
        "restricted-small": ModelRegistration(
            model_id="restricted-small",
            provider_id="mock-provider",
        ),
    }
)


# Temporary application-to-model access policy.
APPLICATION_MODELS: Mapping[str, frozenset[str]] = MappingProxyType(
    {
        "demo-app": frozenset({"local-small"}),
        "test-app": frozenset({"local-small"}),
        "finance-assistant": frozenset({"local-small", "restricted-small"}),
    }
)


def authorize_model_access(
    application_id: str,
    model_id: str,
) -> ModelRegistration:
    """Authorize a trusted application for a registered model."""

    registration = MODEL_REGISTRY.get(model_id)

    if registration is None:
        raise HTTPException(
            status_code=404,
            detail="Model not found.",
        )

    allowed_models = APPLICATION_MODELS.get(
        application_id,
        frozenset(),
    )

    if model_id not in allowed_models:
        raise HTTPException(
            status_code=403,
            detail="Application is not authorized for this model.",
        )

    return registration
