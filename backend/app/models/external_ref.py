from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ExternalProvider(str, enum.Enum):
    ZOHO_BOOKS = "ZOHO_BOOKS"
    RAZORPAY_PAYOUT = "RAZORPAY_PAYOUT"


class ExternalRef(Base):
    """Idempotent map from internal entity → external provider id."""

    __tablename__ = "external_refs"
    __table_args__ = (
        UniqueConstraint("provider", "entity_type", "entity_id", name="uq_external_refs_provider_entity"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False)
    external_id: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
