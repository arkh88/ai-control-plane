"""SQLAlchemy mappings for governance registration tables."""

from datetime import datetime

from sqlalchemy import (
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
