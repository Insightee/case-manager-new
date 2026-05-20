from __future__ import annotations

from typing import Optional

import enum
import json
from datetime import date, datetime, time

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Integer, String, Text, Time, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class CaseAssignmentStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    ENDED = "ENDED"
    TRANSFERRED = "TRANSFERRED"


class BookingMode(str, enum.Enum):
    OPEN = "OPEN"
    FIXED = "FIXED"


class CaseAssignment(Base):
    __tablename__ = "case_assignments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), nullable=False, index=True)
    therapist_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    assigned_by_user_id: Mapped[Optional[int ]] = mapped_column(ForeignKey("users.id"))
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[Optional[date ]] = mapped_column(Date)
    status: Mapped[CaseAssignmentStatus] = mapped_column(
        Enum(CaseAssignmentStatus), default=CaseAssignmentStatus.ACTIVE, index=True
    )
    reason_for_change: Mapped[Optional[str ]] = mapped_column(String(255))
    notes: Mapped[Optional[str ]] = mapped_column(Text)
    booking_mode: Mapped[str] = mapped_column(String(16), default=BookingMode.OPEN.value, nullable=False)
    fixed_weekdays: Mapped[Optional[str]] = mapped_column(Text)
    fixed_start_time: Mapped[Optional[time]] = mapped_column(Time)
    fixed_end_time: Mapped[Optional[time]] = mapped_column(Time)
    fixed_recurrence_group_id: Mapped[Optional[str]] = mapped_column(String(36))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    case = relationship("Case", back_populates="assignments")

    def get_fixed_weekdays(self) -> list[str]:
        if not self.fixed_weekdays:
            return []
        try:
            data = json.loads(self.fixed_weekdays)
            return list(data) if isinstance(data, list) else []
        except json.JSONDecodeError:
            return []

    def set_fixed_weekdays(self, days: list[str]) -> None:
        self.fixed_weekdays = json.dumps(days) if days else None
