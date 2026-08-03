"""Step 6 models: client rate periods, calc exceptions, session add-on kind."""
from __future__ import annotations

import enum
from datetime import date, datetime
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class EffectiveDateChoice(str, enum.Enum):
    START_OF_MONTH = "START_OF_MONTH"
    CHANGE_DATE = "CHANGE_DATE"
    NEXT_SESSION_ONWARD = "NEXT_SESSION_ONWARD"


class AddOnKind(str, enum.Enum):
    MAKE_UP_SESSION = "MAKE_UP_SESSION"
    EXTRA_DAY = "EXTRA_DAY"
    EXTENDED_SESSION = "EXTENDED_SESSION"


class BillingCalcExceptionCode(str, enum.Enum):
    RATE_CHANGE_DATE_UNRESOLVED = "RATE_CHANGE_DATE_UNRESOLVED"
    RATE_PERIOD_GAP = "RATE_PERIOD_GAP"
    RATE_PERIOD_OVERLAP = "RATE_PERIOD_OVERLAP"
    UNKNOWN_LEAVE_TYPE = "UNKNOWN_LEAVE_TYPE"
    MISSING_LEAVE_CREDIT_BALANCE = "MISSING_LEAVE_CREDIT_BALANCE"
    MISSING_ADD_ON_RATE = "MISSING_ADD_ON_RATE"
    ASSIGNMENT_PERIOD_OVERLAP = "ASSIGNMENT_PERIOD_OVERLAP"


class CaseClientRatePeriod(Base):
    """Effective-dated client billing rate. Empty table + current case rate = valid legacy baseline."""

    __tablename__ = "case_client_rate_periods"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), nullable=False, index=True)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[Optional[date]] = mapped_column(Date)  # null = open-ended (inclusive start)
    rate_inr: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    label: Mapped[str] = mapped_column(String(32), nullable=False, default="normal")
    effective_date_choice: Mapped[Optional[str]] = mapped_column(String(32))
    resolved_effective_date: Mapped[Optional[date]] = mapped_column(Date)
    created_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    notes: Mapped[Optional[str]] = mapped_column(Text)


class BillingCalcException(Base):
    """Step 6 calculation exceptions — missing required input, never silent guess."""

    __tablename__ = "billing_calc_exceptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), nullable=False, index=True)
    ledger_month: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    message: Mapped[str] = mapped_column(String(512), nullable=False)
    session_id: Mapped[Optional[int]] = mapped_column(ForeignKey("sessions.id"))
    resolved: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
