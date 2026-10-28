"""API-key authentication for the AI Control Plane."""

import hashlib
import hmac
import os
import re
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

bearer_scheme = HTTPBearer(
    auto_error=False,
    scheme_name="ApplicationAPIKey",
)


@dataclass(frozen=True)
class ApplicationIdentity:
    application_id: str


async def require_application(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
) -> ApplicationIdentity:
    """Validate a Bearer API key and return trusted identity."""

    expected_digest = os.getenv("AICP_API_KEY_SHA256", "")
    application_id = os.getenv("AICP_APP_ID", "demo-app")

    if not re.fullmatch(r"[0-9a-f]{64}", expected_digest) or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}",
        application_id,
    ):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Gateway authentication unavailable.",
        )

    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    received_digest = hashlib.sha256(
        credentials.credentials.encode("utf-8")
    ).hexdigest()

    if not hmac.compare_digest(
        received_digest,
        expected_digest,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return ApplicationIdentity(application_id=application_id)
