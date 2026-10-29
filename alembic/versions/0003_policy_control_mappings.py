"""Add governance controls, policy versions, and reason mappings.

Revision ID: 0003_policy_control_mappings
Revises: 0002_core_governance_tables
"""

import sqlalchemy as sa

from alembic import op

revision: str = "0003_policy_control_mappings"
down_revision: str | None = "0002_core_governance_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "controls",
        sa.Column(
            "control_id",
            sa.String(32),
            primary_key=True,
        ),
        sa.Column(
            "objective",
            sa.String(256),
            nullable=False,
        ),
    )

    op.create_table(
        "policy_versions",
        sa.Column(
            "policy_version",
            sa.String(64),
            primary_key=True,
        ),
        sa.Column(
            "policy_ref",
            sa.String(128),
            nullable=False,
        ),
        sa.Column(
            "description",
            sa.String(256),
            nullable=False,
        ),
    )

    op.create_table(
        "policy_control_mappings",
        sa.Column(
            "policy_version",
            sa.String(64),
            primary_key=True,
        ),
        sa.Column(
            "decision_reason",
            sa.String(64),
            primary_key=True,
        ),
        sa.Column(
            "control_id",
            sa.String(32),
            primary_key=True,
        ),
        sa.ForeignKeyConstraint(
            ["policy_version"],
            ["policy_versions.policy_version"],
            name="fk_pcm_policy_version",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["control_id"],
            ["controls.control_id"],
            name="fk_pcm_control_id",
            ondelete="RESTRICT",
        ),
    )

    op.create_index(
        "ix_pcm_control_id",
        "policy_control_mappings",
        ["control_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_pcm_control_id",
        table_name="policy_control_mappings",
    )
    op.drop_table("policy_control_mappings")
    op.drop_table("policy_versions")
    op.drop_table("controls")
