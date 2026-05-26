from __future__ import annotations

import enum
from datetime import date, datetime
from typing import Optional

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class LeaveType(str, enum.Enum):
    ANNUAL = "ANNUAL"
    SICK = "SICK"
    CASUAL = "CASUAL"
    UNPAID = "UNPAID"


class LeaveBillingCategory(str, enum.Enum):
    PAID = "PAID"
    UNPAID = "UNPAID"
    CARRY_FORWARD = "CARRY_FORWARD"


class LeaveStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class TherapistLeave(Base):
    __tablename__ = "therapist_leaves"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    therapist_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    leave_type: Mapped[LeaveType] = mapped_column(Enum(LeaveType), nullable=False)
    service_line: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    billing_category: Mapped[Optional[LeaveBillingCategory]] = mapped_column(
        Enum(LeaveBillingCategory), nullable=True
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[LeaveStatus] = mapped_column(Enum(LeaveStatus), default=LeaveStatus.PENDING, nullable=False)
    reviewed_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    review_note: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    therapist = relationship("User", foreign_keys=[therapist_user_id])
    reviewer = relationship("User", foreign_keys=[reviewed_by_user_id])
