"""Transactional governance decision evidence for local MVP."""

import os
import sqlite3
from contextlib import closing
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from uuid import uuid4

EvidenceOutcome = Literal["allow", "deny", "error"]


class EvidenceStoreError(Exception):
    """Evidence could not be committed safely."""


@dataclass(frozen=True, slots=True)
class EvidenceRecord:
    request_id: str
    application_id: str
    model_id: str
    outcome: EvidenceOutcome
    reason: str

    evidence_id: str = field(default_factory=lambda: str(uuid4()))
    occurred_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    policy_ref: str = "aicp.authz.decision"


SCHEMA = """
CREATE TABLE IF NOT EXISTS policy_evidence (
    evidence_id TEXT PRIMARY KEY NOT NULL,
    request_id TEXT NOT NULL UNIQUE,
    occurred_at TEXT NOT NULL,
    application_id TEXT NOT NULL,
    model_id TEXT NOT NULL,
    outcome TEXT NOT NULL
        CHECK (outcome IN ('allow', 'deny', 'error')),
    reason TEXT NOT NULL,
    policy_ref TEXT NOT NULL
)
"""


class EvidenceStore:
    """Persist one evidence record per policy-evaluated request."""

    def __init__(self, path: str):
        self.path = path

    def write(self, record: EvidenceRecord) -> None:
        """Return only after the database transaction commits."""

        if not self.path or not Path(self.path).is_absolute():
            raise EvidenceStoreError(
                "A valid absolute evidence database path is required."
            )

        try:
            with closing(sqlite3.connect(self.path, timeout=2.0)) as connection:
                # Prefer durable commits for the local SQLite MVP.
                connection.execute("PRAGMA synchronous=FULL")

                connection.execute(SCHEMA)
                connection.commit()

                with connection:
                    connection.execute(
                        """
                        INSERT INTO policy_evidence (
                            evidence_id,
                            request_id,
                            occurred_at,
                            application_id,
                            model_id,
                            outcome,
                            reason,
                            policy_ref
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            record.evidence_id,
                            record.request_id,
                            record.occurred_at,
                            record.application_id,
                            record.model_id,
                            record.outcome,
                            record.reason,
                            record.policy_ref,
                        ),
                    )

                # Exiting the transaction block successfully
                # means the INSERT was committed.

        except (sqlite3.Error, OSError) as exc:
            raise EvidenceStoreError("Governance evidence persistence failed.") from exc


def get_evidence_store() -> EvidenceStore:
    """Create store from trusted gateway configuration."""
    return EvidenceStore(os.getenv("AICP_EVIDENCE_DB_PATH", ""))
