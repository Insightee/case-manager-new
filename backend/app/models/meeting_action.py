from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class MeetingAction(Base):
    __tablename__ = "meeting_actions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    meeting_id: Mapped[int] = mapped_column(ForeignKey("case_manager_meetings.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    owner_role: Mapped[str] = mapped_column(String(50), nullable=False)  # "parent", "therapist", "case_manager", "admin"
    due_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="open", nullable=False)  # "open", "completed"
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    meeting = relationship("CaseManagerMeeting", back_populates="actions")
