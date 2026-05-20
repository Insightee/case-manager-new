from __future__ import annotations

import enum
import json
from datetime import date, datetime, time
from typing import Optional

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Integer, String, Text, Time, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class RecurringScheduleStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    CANCELLED = "CANCELLED"


class RecurringScheduleAssignment(Base):
    __tablename__ = "recurring_schedule_assignments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), nullable=False, index=True)
    therapist_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    service_type: Mapped[Optional[str]] = mapped_column(String(64))
    product_module: Mapped[Optional[str]] = mapped_column(String(64))
    weekdays_json: Mapped[str] = mapped_column(Text, nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    recurrence_group_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    status: Mapped[RecurringScheduleStatus] = mapped_column(
        Enum(RecurringScheduleStatus), default=RecurringScheduleStatus.ACTIVE, nullable=False
    )
    booked_slot_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    def get_weekdays(self) -> list[str]:
        try:
            data = json.loads(self.weekdays_json)
            return list(data) if isinstance(data, list) else []
        except json.JSONDecodeError:
            return []

    def set_weekdays(self, days: list[str]) -> None:
        self.weekdays_json = json.dumps(days)
