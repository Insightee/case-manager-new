from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ManualLineStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class InvoiceManualLine(Base):
    """One-off therapist payout line items (training, pro-rata, adjustments)."""

    __tablename__ = "invoice_manual_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id"), nullable=False, index=True)
    case_id: Mapped[Optional[int]] = mapped_column(ForeignKey("cases.id"), nullable=True, index=True)
    description: Mapped[str] = mapped_column(String(512), nullable=False)
    quantity: Mapped[float] = mapped_column(Numeric(10, 2), default=1, nullable=False)
    amount_inr: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    pay_share_inr: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    status: Mapped[ManualLineStatus] = mapped_column(
        Enum(ManualLineStatus), default=ManualLineStatus.PENDING, nullable=False
    )
    added_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    approved_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    invoice = relationship("Invoice", back_populates="manual_lines")
