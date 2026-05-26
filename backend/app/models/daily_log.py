from __future__ import annotations

from typing import Optional

import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.visibility import VisibilityStatus


class LogApprovalStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class AttendanceStatus(str, enum.Enum):
    PRESENT = "PRESENT"
    ABSENT = "ABSENT"
    LATE = "LATE"
    PARTIAL = "PARTIAL"


class DailyLog(Base):
    __tablename__ = "daily_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"), unique=True, nullable=False)
    attendance_status: Mapped[str] = mapped_column(String(64), nullable=False)
    activities_done: Mapped[Optional[str ]] = mapped_column(Text)
    session_notes: Mapped[Optional[str]] = mapped_column(Text)
    goals_addressed: Mapped[Optional[str]] = mapped_column(Text)
    observations: Mapped[Optional[str ]] = mapped_column(Text)
    follow_ups: Mapped[Optional[str]] = mapped_column(Text)
    parent_notes: Mapped[Optional[str ]] = mapped_column(Text)
    parent_session_rating: Mapped[Optional[int]] = mapped_column(Integer)
    parent_feedback: Mapped[Optional[str]] = mapped_column(Text)
    parent_feedback_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    parent_feedback_public: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    submitted_at: Mapped[Optional[datetime ]] = mapped_column(DateTime(timezone=True), index=True)
    approval_status: Mapped[LogApprovalStatus] = mapped_column(Enum(LogApprovalStatus), default=LogApprovalStatus.PENDING)
    late_addition: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    late_reason: Mapped[Optional[str]] = mapped_column(Text)
    review_note: Mapped[Optional[str]] = mapped_column(Text)
    visibility_status: Mapped[VisibilityStatus] = mapped_column(
        Enum(VisibilityStatus), default=VisibilityStatus.INTERNAL_ONLY, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    session = relationship("Session", back_populates="daily_log")
