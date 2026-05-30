from __future__ import annotations

from typing import Optional

import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.visibility import VisibilityStatus


class InvoiceStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    IN_REVIEW = "IN_REVIEW"
    APPROVED = "APPROVED"
    PAID = "PAID"
    QUERIED = "QUERIED"
    REJECTED = "REJECTED"


class Invoice(Base):
    __tablename__ = "invoices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    therapist_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    month: Mapped[str] = mapped_column(String(32), nullable=False)
    amount_inr: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    subtotal_inr: Mapped[Optional[float]] = mapped_column(Numeric(12, 2))
    leave_deduction_inr: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), default=0)
    adjustment_inr: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), default=0)
    paid_amount_inr: Mapped[Optional[float]] = mapped_column(Numeric(12, 2))
    sessions_count: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[InvoiceStatus] = mapped_column(Enum(InvoiceStatus), default=InvoiceStatus.DRAFT)
    reviewer_comment: Mapped[Optional[str ]] = mapped_column(Text)
    visibility_status: Mapped[VisibilityStatus] = mapped_column(Enum(VisibilityStatus), default=VisibilityStatus.INTERNAL_ONLY)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    case_lines = relationship("InvoiceCaseLine", back_populates="invoice", cascade="all, delete-orphan")
    manual_lines = relationship("InvoiceManualLine", back_populates="invoice", cascade="all, delete-orphan")
