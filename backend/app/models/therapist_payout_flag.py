from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class TherapistPayoutFlag(Base):
    __tablename__ = "therapist_payout_flags"
    __table_args__ = (
        Index(
            "ix_therapist_payout_flags_active_month",
            "therapist_user_id",
            "billing_month",
            "is_active",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    therapist_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )
    billing_month: Mapped[str] = mapped_column(String(7), nullable=False, index=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), nullable=False, index=True)
    outgoing_assignment_id: Mapped[int] = mapped_column(
        ForeignKey("case_assignments.id"), nullable=False
    )
    flagged_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )
    reason: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    cleared_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    cleared_invoice_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("invoices.id")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
