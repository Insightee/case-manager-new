"""Machine principals for external integrations (API + MCP)."""
from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class IntegrationClientStatus(str, enum.Enum):
    ACTIVE = "active"
    REVOKED = "revoked"


# Explicit allow-list; never grant admin.override or write scopes in Phase B.
INTEGRATION_SCOPES: frozenset[str] = frozenset(
    {
        "cases:read",
        "reports:read",
        "sessions:summarize",
        "reporting:pending",
        "ops:summary",
    }
)


class IntegrationClient(Base):
    __tablename__ = "integration_clients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=IntegrationClientStatus.ACTIVE.value, index=True)
    scopes_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    rate_limit_per_minute: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    created_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    credentials = relationship("IntegrationCredential", back_populates="client", cascade="all, delete-orphan")
    case_grants = relationship("IntegrationCaseGrant", back_populates="client", cascade="all, delete-orphan")

    @property
    def scopes(self) -> list[str]:
        raw = self.scopes_json or []
        return [str(s) for s in raw if str(s) in INTEGRATION_SCOPES]

    @property
    def is_active(self) -> bool:
        return self.status == IntegrationClientStatus.ACTIVE.value


class IntegrationCredential(Base):
    __tablename__ = "integration_credentials"
    __table_args__ = (UniqueConstraint("public_client_id", name="uq_integration_credentials_public_client_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    integration_client_id: Mapped[int] = mapped_column(
        ForeignKey("integration_clients.id", ondelete="CASCADE"), nullable=False, index=True
    )
    public_client_id: Mapped[str] = mapped_column(String(64), nullable=False)
    secret_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    client = relationship("IntegrationClient", back_populates="credentials")

    @property
    def is_usable(self) -> bool:
        if self.revoked_at is not None:
            return False
        if self.expires_at is None:
            return True
        from datetime import datetime, timezone

        exp = self.expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        return exp >= datetime.now(timezone.utc)


class IntegrationCaseGrant(Base):
    __tablename__ = "integration_case_grants"
    __table_args__ = (
        UniqueConstraint(
            "integration_client_id",
            "case_id",
            name="uq_integration_case_grants_client_case",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    integration_client_id: Mapped[int] = mapped_column(
        ForeignKey("integration_clients.id", ondelete="CASCADE"), nullable=False
    )
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    client = relationship("IntegrationClient", back_populates="case_grants")
