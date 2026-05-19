from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ParentBillingStatus(str, enum.Enum):
    DUE = "DUE"
    PAID = "PAID"


class ParentBillingStatement(Base):
    """Family-facing billing summary (not therapist payout invoices)."""

    __tablename__ = "parent_billing_statements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    parent_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    case_id: Mapped[Optional[int]] = mapped_column(ForeignKey("cases.id"), nullable=True, index=True)
    month: Mapped[str] = mapped_column(String(32), nullable=False)
    amount_inr: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[ParentBillingStatus] = mapped_column(Enum(ParentBillingStatus), default=ParentBillingStatus.DUE)
    detail: Mapped[Optional[str]] = mapped_column(String(512))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
