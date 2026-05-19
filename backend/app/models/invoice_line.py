from __future__ import annotations

import enum
from datetime import date, datetime
from typing import Optional

from sqlalchemy import JSON, Boolean, Date, DateTime, Enum, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class SessionLineType(str, enum.Enum):
    INCLUDED = "INCLUDED"
    ADDITIONAL = "ADDITIONAL"
    PER_SESSION = "PER_SESSION"


class SessionLineSource(str, enum.Enum):
    LOG = "LOG"
    MANUAL_LATE = "MANUAL_LATE"
    ADJUSTMENT = "ADJUSTMENT"


class InvoiceCaseLine(Base):
    __tablename__ = "invoice_case_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id"), nullable=False, index=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), nullable=False)
    case_code: Mapped[str] = mapped_column(String(32), nullable=False)
    billing_type: Mapped[str] = mapped_column(String(32), nullable=False)
    included_sessions: Mapped[int] = mapped_column(Integer, default=0)
    additional_sessions: Mapped[int] = mapped_column(Integer, default=0)
    therapist_share_inr: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    billing_snapshot: Mapped[Optional[dict]] = mapped_column(JSON)

    invoice = relationship("Invoice", back_populates="case_lines")
    session_lines = relationship("InvoiceSessionLine", back_populates="case_line", cascade="all, delete-orphan")


class InvoiceSessionLine(Base):
    __tablename__ = "invoice_session_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    invoice_case_line_id: Mapped[int] = mapped_column(ForeignKey("invoice_case_lines.id"), nullable=False, index=True)
    session_id: Mapped[Optional[int]] = mapped_column(ForeignKey("sessions.id"))
    daily_log_id: Mapped[Optional[int]] = mapped_column(ForeignKey("daily_logs.id"))
    session_date: Mapped[date] = mapped_column(Date, nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=60)
    line_type: Mapped[SessionLineType] = mapped_column(Enum(SessionLineType), nullable=False)
    amount_inr: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    source: Mapped[SessionLineSource] = mapped_column(Enum(SessionLineSource), default=SessionLineSource.LOG)
    included: Mapped[bool] = mapped_column(Boolean, default=True)
    flags: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    case_line = relationship("InvoiceCaseLine", back_populates="session_lines")
