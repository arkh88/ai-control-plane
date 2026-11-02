"""Async PostgreSQL adapter for the gateway evidence contract."""

from sqlalchemy.ext.asyncio import AsyncEngine

from app.async_decision_repository import AsyncDecisionRepository
from app.decision_repository import DecisionRepositoryError
from app.evidence import EvidenceRecord, EvidenceStoreError


class PostgresEvidenceStore:
    """Commit evidence through native async PostgreSQL I/O."""

    def __init__(self, engine: AsyncEngine) -> None:
        self.repository = AsyncDecisionRepository(engine)

    async def write(self, record: EvidenceRecord) -> None:
        try:
            await self.repository.write(record)

        except DecisionRepositoryError as exc:
            raise EvidenceStoreError("Governance evidence persistence failed.") from exc
