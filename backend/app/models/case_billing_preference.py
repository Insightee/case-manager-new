from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class CaseBillingPreference(Base):
    """Remembered billing choices per case for faster repeat invoicing."""

    __tablename__ = "case_billing_preferences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), unique=True, nullable=False, index=True)
    invoice_type: Mapped[Optional[str]] = mapped_column(String(32))
    gst_applicable: Mapped[Optional[bool]] = mapped_column(Boolean)
    gst_rate_percent: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    gateway_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    due_date_offset_days: Mapped[Optional[int]] = mapped_column(Integer)
    payment_policy_template: Mapped[Optional[str]] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
