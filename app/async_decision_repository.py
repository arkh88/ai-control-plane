"""Native asynchronous PostgreSQL decision repository.

Runtime evidence must commit before approved inference.
"""

from datetime import datetime

from sqlalchemy import insert, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine

from app.decision_repository import (
    DecisionRepositoryError,
    StoredDecision,
)
from app.evidence import EvidenceRecord
from app.governance_controls import controls_for_reason
from app.governance_models import GovernanceDecision


class AsyncDecisionRepository:
    """Perform transactional decision I/O without blocking the event loop."""

    def __init__(self, engine: AsyncEngine) -> None:
        self.engine = engine

    async def write(self, record: EvidenceRecord) -> None:
        """Return only after PostgreSQL confirms transaction commit."""

        try:
            control_ids = list(controls_for_reason(record.reason))

            occurred_at = datetime.fromisoformat(record.occurred_at)

            if occurred_at.tzinfo is None or occurred_at.utcoffset() is None:
                raise ValueError("Evidence timestamp must include timezone.")

            async with self.engine.begin() as connection:
                await connection.execute(
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
                        control_ids=control_ids,
                    )
                )

            # The transaction context has exited successfully.
            # PostgreSQL has acknowledged the commit.

        except (SQLAlchemyError, ValueError) as exc:
            raise DecisionRepositoryError("Governance decision commit failed.") from exc

    async def get_by_request_id(
        self,
        request_id: str,
    ) -> StoredDecision | None:
        """Read an already committed authorization decision."""

        try:
            async with self.engine.connect() as connection:
                result = await connection.execute(
                    select(GovernanceDecision.__table__).where(
                        GovernanceDecision.request_id == request_id
                    )
                )

                row = result.mappings().one_or_none()

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
