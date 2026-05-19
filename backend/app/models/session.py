from __future__ import annotations

from typing import Optional

import enum
from datetime import date, datetime, time

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Integer, Time, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class SessionMode(str, enum.Enum):
    HOME = "HOME"
    SCHOOL = "SCHOOL"
    CENTER = "CENTER"
    ONLINE = "ONLINE"


class SessionStatus(str, enum.Enum):
    SCHEDULED = "SCHEDULED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    NO_SHOW = "NO_SHOW"
    RESCHEDULED = "RESCHEDULED"


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), nullable=False, index=True)
    therapist_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    scheduled_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    start_time: Mapped[Optional[time ]] = mapped_column(Time)
    end_time: Mapped[Optional[time ]] = mapped_column(Time)
    mode: Mapped[SessionMode] = mapped_column(Enum(SessionMode), default=SessionMode.HOME)
    status: Mapped[SessionStatus] = mapped_column(Enum(SessionStatus), default=SessionStatus.SCHEDULED)
    actual_start_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    actual_end_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    auto_ended: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    case = relationship("Case", back_populates="sessions", lazy="joined")
    daily_log = relationship("DailyLog", back_populates="session", uselist=False)
