"""Create durable governance authorization decisions.

Revision ID: 0004_governance_decisions
Revises: 0003_policy_control_mappings
"""

import sqlalchemy as sa

from alembic import op

revision: str = "0004_governance_decisions"
down_revision: str | None = "0003_policy_control_mappings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "decisions",
        sa.Column(
            "evidence_id",
            sa.String(36),
            primary_key=True,
        ),
        sa.Column(
            "request_id",
            sa.String(36),
            nullable=False,
        ),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "application_id",
            sa.String(128),
            nullable=False,
        ),
        sa.Column(
            "model_id",
            sa.String(256),
            nullable=False,
        ),
        sa.Column(
            "outcome",
            sa.String(16),
            nullable=False,
        ),
        sa.Column(
            "reason",
            sa.String(64),
            nullable=False,
        ),
        sa.Column(
            "policy_ref",
            sa.String(128),
            nullable=False,
        ),
        sa.Column(
            "policy_version",
            sa.String(64),
            nullable=False,
        ),
        sa.Column(
            "control_ids",
            sa.JSON(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "request_id",
            name="uq_decisions_request_id",
        ),
        sa.CheckConstraint(
            "outcome IN ('allow', 'deny', 'error')",
            name="ck_decisions_outcome",
        ),
    )

    op.create_index(
        "ix_decisions_occurred_at",
        "decisions",
        ["occurred_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_decisions_occurred_at",
        table_name="decisions",
    )
    op.drop_table("decisions")
