from __future__ import annotations

from typing import Optional

import enum
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class CaseAssignmentStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    ENDED = "ENDED"
    TRANSFERRED = "TRANSFERRED"


class CaseAssignment(Base):
    __tablename__ = "case_assignments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), nullable=False, index=True)
    therapist_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    assigned_by_user_id: Mapped[Optional[int ]] = mapped_column(ForeignKey("users.id"))
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[Optional[date ]] = mapped_column(Date)
    status: Mapped[CaseAssignmentStatus] = mapped_column(Enum(CaseAssignmentStatus), default=CaseAssignmentStatus.ACTIVE)
    reason_for_change: Mapped[Optional[str ]] = mapped_column(String(255))
    notes: Mapped[Optional[str ]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    case = relationship("Case", back_populates="assignments")
