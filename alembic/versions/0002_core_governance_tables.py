"""Create applications, API credential digests, and models.

Revision ID: 0002_core_governance_tables
Revises: 0001_governance_baseline
"""

import sqlalchemy as sa

from alembic import op

revision: str = "0002_core_governance_tables"
down_revision: str | None = "0001_governance_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create the core governance registration tables."""

    op.create_table(
        "applications",
        sa.Column(
            "application_id",
            sa.String(64),
            primary_key=True,
        ),
        sa.Column(
            "display_name",
            sa.String(128),
            nullable=False,
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
    )

    op.create_table(
        "models",
        sa.Column(
            "model_id",
            sa.String(64),
            primary_key=True,
        ),
        sa.Column(
            "provider_id",
            sa.String(64),
            nullable=False,
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
    )

    op.create_table(
        "api_credentials",
        sa.Column(
            "credential_id",
            sa.String(64),
            primary_key=True,
        ),
        sa.Column(
            "application_id",
            sa.String(64),
            nullable=False,
        ),
        sa.Column(
            "key_sha256",
            sa.String(64),
            nullable=False,
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["applications.application_id"],
            name="fk_api_credentials_application_id",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "key_sha256",
            name="uq_api_credentials_key_sha256",
        ),
        sa.CheckConstraint(
            "length(key_sha256) = 64",
            name="ck_api_credentials_digest_length",
        ),
    )

    op.create_index(
        "ix_api_credentials_application_id",
        "api_credentials",
        ["application_id"],
    )


def downgrade() -> None:
    """Remove the core tables in reverse dependency order."""

    op.drop_index(
        "ix_api_credentials_application_id",
        table_name="api_credentials",
    )
    op.drop_table("api_credentials")
    op.drop_table("models")
    op.drop_table("applications")
