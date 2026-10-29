"""Transactional SQLAlchemy repository for governance decisions.

Day 28: tested independently of the live inference gateway.
"""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import Engine, insert, select
from sqlalchemy.exc import SQLAlchemyError

from app.evidence import EvidenceRecord
from app.governance_controls import controls_for_reason
from app.governance_models import GovernanceDecision


class DecisionRepositoryError(Exception):
    """A governance decision could not be persisted or read."""


@dataclass(frozen=True, slots=True)
class StoredDecision:
    evidence_id: str
    request_id: str
    occurred_at: datetime
    application_id: str
    model_id: str
    outcome: str
    reason: str
    policy_ref: str
    policy_version: str
    control_ids: tuple[str, ...]


class PostgresDecisionRepository:
    """Store decisions atomically in a SQLAlchemy database."""

    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def write(self, record: EvidenceRecord) -> None:
        """Return only after the database transaction commits."""

        try:
            controls = list(controls_for_reason(record.reason))
            occurred_at = datetime.fromisoformat(record.occurred_at)

            if occurred_at.tzinfo is None or occurred_at.utcoffset() is None:
                raise ValueError("Evidence timestamp must include a timezone.")

            with self.engine.begin() as connection:
                connection.execute(
                    insert(GovernanceDecision).values(
                        evidence_id=record.evidence_id,
                        request_id=record.request_id,
                        occurred_at=occurred_at,
                        application_id=record.application_id,
                        model_id=record.model_id,
                        outcome=record.outcome,
                        reason=record.reason,
                        policy_ref=record.policy_ref,
                        policy_version=record.policy_version,
                        control_ids=controls,
                    )
                )

        except (SQLAlchemyError, ValueError) as exc:
            raise DecisionRepositoryError("Governance decision commit failed.") from exc

    def get_by_request_id(
        self,
        request_id: str,
    ) -> StoredDecision | None:
        """Read a previously committed decision."""

        try:
            with self.engine.connect() as connection:
                row = (
                    connection.execute(
                        select(GovernanceDecision.__table__).where(
                            GovernanceDecision.request_id == request_id
                        )
                    )
                    .mappings()
                    .one_or_none()
                )

            if row is None:
                return None

            return StoredDecision(
                evidence_id=row["evidence_id"],
                request_id=row["request_id"],
                occurred_at=row["occurred_at"],
                application_id=row["application_id"],
                model_id=row["model_id"],
                outcome=row["outcome"],
                reason=row["reason"],
                policy_ref=row["policy_ref"],
                policy_version=row["policy_version"],
                control_ids=tuple(row["control_ids"]),
            )

        except (SQLAlchemyError, ValueError, TypeError) as exc:
            raise DecisionRepositoryError("Governance decision lookup failed.") from exc
