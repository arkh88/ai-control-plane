"""Initialize governance database migration tracking.

Revision ID: 0001_governance_baseline
Revises:
"""

from collections.abc import Sequence

revision: str = "0001_governance_baseline"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Baseline: no application tables exist yet."""


def downgrade() -> None:
    """Nothing to remove from this empty baseline."""
