"""Transactional governance evidence with schema migration."""

import json
import os
import sqlite3
from contextlib import closing
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, Protocol
from uuid import uuid4

from fastapi import HTTPException, Request

from app.governance_controls import controls_for_reason

EvidenceOutcome = Literal["allow", "deny", "error"]


class EvidenceStoreError(Exception):
    """Governance evidence could not be committed."""


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
    policy_version: str = "not_reported"


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
    policy_ref TEXT NOT NULL,
    policy_version TEXT NOT NULL DEFAULT 'not_reported',
    control_ids TEXT NOT NULL DEFAULT '[]'
)
"""


class EvidenceStore:
    """Commit an authorization record before inference."""

    def __init__(self, path: str):
        self.path = path

    def write(self, record: EvidenceRecord) -> None:
        if not self.path or not Path(self.path).is_absolute():
            raise EvidenceStoreError("An absolute evidence database path is required.")

        try:
            control_ids = controls_for_reason(record.reason)
            control_ids_json = json.dumps(list(control_ids))

            with closing(sqlite3.connect(self.path, timeout=2.0)) as connection:
                connection.execute("PRAGMA synchronous=FULL")

                with connection:
                    # Create the complete table for a new database.
                    connection.execute(SCHEMA)

                    # Upgrade existing Day 20 databases in place.
                    existing_columns = {
                        row[1]
                        for row in connection.execute(
                            "PRAGMA table_info(policy_evidence)"
                        )
                    }

                    if "policy_version" not in existing_columns:
                        connection.execute(
                            "ALTER TABLE policy_evidence "
                            "ADD COLUMN policy_version TEXT "
                            "NOT NULL DEFAULT 'not_reported'"
                        )

                    if "control_ids" not in existing_columns:
                        connection.execute(
                            "ALTER TABLE policy_evidence "
                            "ADD COLUMN control_ids TEXT "
                            "NOT NULL DEFAULT '[]'"
                        )

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
                            policy_ref,
                            policy_version,
                            control_ids
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                            record.policy_version,
                            control_ids_json,
                        ),
                    )

                # Successful exit commits the migration and INSERT.
                # No model call may occur before write() returns.

        except (sqlite3.Error, OSError, ValueError) as exc:
            raise EvidenceStoreError("Governance evidence persistence failed.") from exc


class AsyncEvidenceWriter(Protocol):
    """Asynchronous evidence-writing contract."""

    async def write(self, record: EvidenceRecord) -> None:
        """Commit the record or raise an evidence error."""
        ...


def get_evidence_store(
    request: Request,
) -> EvidenceStore | AsyncEvidenceWriter:
    """Select the configured evidence store without fallback."""

    backend = os.getenv("AICP_EVIDENCE_BACKEND")

    if backend == "sqlite":
        return EvidenceStore(os.getenv("AICP_EVIDENCE_DB_PATH", ""))

    if backend == "postgres":
        from app.postgres_evidence import PostgresEvidenceStore

        engine = getattr(
            request.app.state,
            "governance_async_engine",
            None,
        )

        if engine is None:
            raise HTTPException(
                status_code=503,
                detail="Governance evidence unavailable.",
            )

        return PostgresEvidenceStore(engine)

    raise HTTPException(
        status_code=503,
        detail="Governance evidence unavailable.",
    )
