from __future__ import annotations

import enum
from datetime import date, datetime, time
from typing import Optional

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Integer, String, Text, Time, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class SlotStatus(str, enum.Enum):
    AVAILABLE = "AVAILABLE"
    BOOKED = "BOOKED"
    BLOCKED = "BLOCKED"


class BookingSource(str, enum.Enum):
    THERAPIST = "THERAPIST"
    ADMIN = "ADMIN"
    PARENT = "PARENT"
    SYSTEM = "SYSTEM"


class TherapistSlot(Base):
    __tablename__ = "therapist_slots"
    __table_args__ = (
        UniqueConstraint("therapist_user_id", "slot_date", "start_time", name="uq_therapist_slot_datetime"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    therapist_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    slot_date: Mapped[date] = mapped_column(Date, nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    status: Mapped[SlotStatus] = mapped_column(Enum(SlotStatus), default=SlotStatus.AVAILABLE, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    case_id: Mapped[Optional[int]] = mapped_column(ForeignKey("cases.id"), nullable=True, index=True)
    booked_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    booking_source: Mapped[Optional[BookingSource]] = mapped_column(Enum(BookingSource), nullable=True)
    recurrence_group_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    slot_duration_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    therapist = relationship("User", foreign_keys=[therapist_user_id])
    case = relationship("Case", foreign_keys=[case_id])
    booked_by = relationship("User", foreign_keys=[booked_by_user_id])
