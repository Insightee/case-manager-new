from __future__ import annotations

import enum
from datetime import date, datetime, time
from typing import Optional

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Integer, String, Text, Time, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class MeetingType(str, enum.Enum):
    CLIENT_ONLY = "CLIENT_ONLY"
    CLIENT_AND_THERAPIST = "CLIENT_AND_THERAPIST"
    SUPERVISION = "SUPERVISION"
    IEP_MEETING = "IEP_MEETING"


class MeetingStatus(str, enum.Enum):
    SCHEDULED = "SCHEDULED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class CaseManagerMeeting(Base):
    __tablename__ = "case_manager_meetings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_manager_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    case_id: Mapped[Optional[int]] = mapped_column(ForeignKey("cases.id"), nullable=True, index=True)
    parent_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    therapist_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)

    scheduled_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    scheduled_time: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    meeting_type: Mapped[MeetingType] = mapped_column(
        Enum(MeetingType), default=MeetingType.CLIENT_ONLY, nullable=False
    )
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    meeting_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    guest_emails_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    staff_attendee_user_ids_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    notes_concerns: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notes_follow_up: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notes_action: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notes_other: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    status: Mapped[MeetingStatus] = mapped_column(
        Enum(MeetingStatus), default=MeetingStatus.SCHEDULED, nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), onupdate=func.now())

    case_manager = relationship("User", foreign_keys=[case_manager_user_id], lazy="joined")
    case = relationship("Case", foreign_keys=[case_id], lazy="select")
    parent_user = relationship("User", foreign_keys=[parent_user_id], lazy="select")
    therapist_user = relationship("User", foreign_keys=[therapist_user_id], lazy="select")
