from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, JSON, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class BillingMonthCloseStatus(str, enum.Enum):
    CLOSED = "CLOSED"


class BillingMonthClose(Base):
    """Frozen finance export for a billing month (payout preview rows, etc.)."""

    __tablename__ = "billing_month_closes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    billing_month: Mapped[str] = mapped_column(String(32), nullable=False, unique=True, index=True)
    status: Mapped[BillingMonthCloseStatus] = mapped_column(
        Enum(BillingMonthCloseStatus), default=BillingMonthCloseStatus.CLOSED
    )
    payout_preview_rows: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    closed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    closed_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    notes: Mapped[Optional[str]] = mapped_column(Text)

    __table_args__ = (UniqueConstraint("billing_month", name="uq_billing_month_closes_month"),)


class CaseBillingPeriodSnapshot(Base):
    """Per-case billing context frozen at month close or client invoice send."""

    __tablename__ = "case_billing_period_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), nullable=False, index=True)
    billing_month: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    billing_snapshot: Mapped[Optional[dict]] = mapped_column(JSON)
    client_invoice_id: Mapped[Optional[int]] = mapped_column(ForeignKey("client_invoices.id"), index=True)
    ledger_subtotal_inr: Mapped[Optional[float]] = mapped_column(Numeric(12, 2))
    ledger_tax_inr: Mapped[Optional[float]] = mapped_column(Numeric(12, 2))
    ledger_total_inr: Mapped[Optional[float]] = mapped_column(Numeric(12, 2))
    margin_inr: Mapped[Optional[float]] = mapped_column(Numeric(12, 2))
    therapist_payout_total_inr: Mapped[Optional[float]] = mapped_column(Numeric(12, 2))
    session_count: Mapped[Optional[int]] = mapped_column(Integer)
    closed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    closed_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))

    __table_args__ = (
        UniqueConstraint("case_id", "billing_month", name="uq_case_billing_period_snapshots_case_month"),
    )
