from __future__ import annotations

import enum
from datetime import date, datetime
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PackageBillingMode(str, enum.Enum):
    PACKAGE = "PACKAGE"
    HOMECARE_PER_SESSION = "HOMECARE_PER_SESSION"


class ClientPackageCycle(Base):
    """Per-cycle package drawdown with optional credit-forward rollover."""

    __tablename__ = "client_package_cycles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    care_package_id: Mapped[int] = mapped_column(ForeignKey("care_packages.id"), nullable=False, index=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), nullable=False, index=True)
    cycle_index: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    billed_sessions: Mapped[int] = mapped_column(Integer, nullable=False)
    consumed_sessions: Mapped[int] = mapped_column(Integer, default=0)
    remaining_sessions: Mapped[int] = mapped_column(Integer, nullable=False)
    carry_forward_count: Mapped[int] = mapped_column(Integer, default=0)
    expires_on: Mapped[Optional[date]] = mapped_column(Date)
    needs_review: Mapped[bool] = mapped_column(Boolean, default=False)
    billing_mode: Mapped[str] = mapped_column(String(32), default=PackageBillingMode.PACKAGE.value)
    client_invoice_id: Mapped[Optional[int]] = mapped_column(ForeignKey("client_invoices.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
