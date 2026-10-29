"""SQLAlchemy mappings for governance registration tables."""

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
)


class Base(DeclarativeBase):
    """Shared metadata for governance ORM mappings."""


class Application(Base):
    __tablename__ = "applications"

    application_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
    )

    credentials: Mapped[list["ApiCredential"]] = relationship(
        back_populates="application"
    )


class ApiCredential(Base):
    __tablename__ = "api_credentials"

    __table_args__ = (
        UniqueConstraint(
            "key_sha256",
            name="uq_api_credentials_key_sha256",
        ),
        CheckConstraint(
            "length(key_sha256) = 64",
            name="ck_api_credentials_digest_length",
        ),
        Index(
            "ix_api_credentials_application_id",
            "application_id",
        ),
    )

    credential_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    application_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey(
            "applications.application_id",
            name="fk_api_credentials_application_id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    key_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.current_timestamp(),
    )

    application: Mapped[Application] = relationship(back_populates="credentials")


class Model(Base):
    __tablename__ = "models"

    model_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    provider_id: Mapped[str] = mapped_column(String(64), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
    )


class GovernanceControl(Base):
    """An internal governance control, not a certification."""

    __tablename__ = "controls"

    control_id: Mapped[str] = mapped_column(
        String(32),
        primary_key=True,
    )
    objective: Mapped[str] = mapped_column(
        String(256),
        nullable=False,
    )

    mappings: Mapped[list["PolicyControlMapping"]] = relationship(
        back_populates="control"
    )


class GovernancePolicyVersion(Base):
    """A reported policy version and logical OPA policy reference."""

    __tablename__ = "policy_versions"

    policy_version: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
    )
    policy_ref: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )
    description: Mapped[str] = mapped_column(
        String(256),
        nullable=False,
    )

    mappings: Mapped[list["PolicyControlMapping"]] = relationship(
        back_populates="policy"
    )


class PolicyControlMapping(Base):
    """Relate an OPA decision reason to a governance control."""

    __tablename__ = "policy_control_mappings"

    __table_args__ = (Index("ix_pcm_control_id", "control_id"),)

    policy_version: Mapped[str] = mapped_column(
        String(64),
        ForeignKey(
            "policy_versions.policy_version",
            name="fk_pcm_policy_version",
            ondelete="RESTRICT",
        ),
        primary_key=True,
    )

    decision_reason: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
    )

    control_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey(
            "controls.control_id",
            name="fk_pcm_control_id",
            ondelete="RESTRICT",
        ),
        primary_key=True,
    )

    policy: Mapped[GovernancePolicyVersion] = relationship(back_populates="mappings")
    control: Mapped[GovernanceControl] = relationship(back_populates="mappings")


class GovernanceDecision(Base):
    """Durable authorization decision evidence."""

    __tablename__ = "decisions"

    __table_args__ = (
        UniqueConstraint(
            "request_id",
            name="uq_decisions_request_id",
        ),
        CheckConstraint(
            "outcome IN ('allow', 'deny', 'error')",
            name="ck_decisions_outcome",
        ),
        Index(
            "ix_decisions_occurred_at",
            "occurred_at",
        ),
    )

    evidence_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
    )
    request_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    application_id: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )
    model_id: Mapped[str] = mapped_column(
        String(256),
        nullable=False,
    )
    outcome: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
    )
    reason: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    policy_ref: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )
    policy_version: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    control_ids: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
    )
