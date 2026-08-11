"""Configurable tolerance/severity rules for billing readiness exceptions (read by approve-gate in loop 3)."""
from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class BillingReadinessExceptionType(str, enum.Enum):
    SESSION_COUNT_MISMATCH = "SESSION_COUNT_MISMATCH"
    LEAVE_MISMATCH = "LEAVE_MISMATCH"
    INVOICE_ENGINE_AMOUNT_MISMATCH = "INVOICE_ENGINE_AMOUNT_MISMATCH"
    MISSING_INVOICE_NUMBER = "MISSING_INVOICE_NUMBER"
    REPORTS_NOT_SUBMITTED = "REPORTS_NOT_SUBMITTED"
    STATUS_CONFLICT = "STATUS_CONFLICT"


class BillingReadinessExceptionSeverity(str, enum.Enum):
    WARN = "WARN"
    BLOCK = "BLOCK"


class BillingReadinessExceptionRule(Base):
    __tablename__ = "billing_readiness_exception_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    exception_type: Mapped[BillingReadinessExceptionType] = mapped_column(
        Enum(BillingReadinessExceptionType),
        nullable=False,
        unique=True,
    )
    tolerance: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    severity: Mapped[BillingReadinessExceptionSeverity] = mapped_column(
        Enum(BillingReadinessExceptionSeverity),
        nullable=False,
        default=BillingReadinessExceptionSeverity.WARN,
    )
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
