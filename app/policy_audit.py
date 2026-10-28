"""Structured operational logging for OPA decisions."""

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Literal

PolicyOutcome = Literal["allow", "deny", "error"]

audit_logger = logging.getLogger("aicp.policy")
audit_logger.setLevel(logging.INFO)
audit_logger.propagate = False

# Send compact JSON records to container stdout.
if not audit_logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))
    audit_logger.addHandler(handler)


def log_policy_event(
    *,
    request_id: str,
    application_id: str,
    model_id: str,
    outcome: PolicyOutcome,
    reason: str,
) -> None:
    """Emit a minimal structured policy-decision event."""

    event = {
        "event": "policy_decision",
        "timestamp": datetime.now(UTC).isoformat(),
        "request_id": request_id,
        "application_id": application_id,
        "model_id": model_id,
        "policy_engine": "opa",
        "outcome": outcome,
        "reason": reason,
    }

    audit_logger.info(
        json.dumps(
            event,
            separators=(",", ":"),
            ensure_ascii=True,
        )
    )
