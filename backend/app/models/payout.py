from __future__ import annotations

from typing import Optional

import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PayoutStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    PAID = "PAID"


class Payout(Base):
    __tablename__ = "payouts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    therapist_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    invoice_id: Mapped[Optional[int ]] = mapped_column(ForeignKey("invoices.id"))
    amount_inr: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    paid_amount_inr: Mapped[Optional[float ]] = mapped_column(Numeric(12, 2))
    status: Mapped[PayoutStatus] = mapped_column(Enum(PayoutStatus), default=PayoutStatus.PENDING)
    payslip_path: Mapped[Optional[str ]] = mapped_column(String(512))
    notes: Mapped[Optional[str ]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
