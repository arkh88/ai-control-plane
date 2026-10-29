"""Internal governance control references.

These IDs are project-specific, not external certifications.
"""

from types import MappingProxyType

CONTROL_CATALOG = MappingProxyType(
    {
        "AICP-AC-001": "Application-to-model authorization",
        "AICP-RT-001": "Trusted model routing",
        "AICP-FC-001": "Fail-closed policy evaluation",
        "AICP-EV-001": "Evidence committed before inference",
    }
)

CONTROL_BY_REASON = MappingProxyType(
    {
        "ALLOW": ("AICP-AC-001", "AICP-EV-001"),
        "MODEL_NOT_ALLOWED": (
            "AICP-AC-001",
            "AICP-EV-001",
        ),
        "UNKNOWN_APPLICATION": (
            "AICP-AC-001",
            "AICP-EV-001",
        ),
        "MODEL_NOT_REGISTERED": (
            "AICP-AC-001",
            "AICP-RT-001",
            "AICP-EV-001",
        ),
        "POLICY_EVALUATION_ERROR": (
            "AICP-FC-001",
            "AICP-EV-001",
        ),
        "ROUTE_UNAVAILABLE": (
            "AICP-RT-001",
            "AICP-EV-001",
        ),
    }
)


def controls_for_reason(reason: str) -> tuple[str, ...]:
    """Return control references for a decision reason."""

    try:
        controls = CONTROL_BY_REASON[reason]
    except KeyError as exc:
        raise ValueError(f"No governance mapping for reason: {reason}") from exc

    if not all(control in CONTROL_CATALOG for control in controls):
        raise ValueError("Unknown governance control reference.")

    return controls
