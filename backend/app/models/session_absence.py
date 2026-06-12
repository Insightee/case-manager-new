from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class SessionAbsenceType(str, enum.Enum):
    THERAPIST_LEAVE = "THERAPIST_LEAVE"
    CLIENT_ABSENT = "CLIENT_ABSENT"


class SessionAbsenceStatus(str, enum.Enum):
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class SessionAbsenceRequest(Base):
    __tablename__ = "session_absence_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"), nullable=False, index=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), nullable=False, index=True)
    therapist_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    absence_type: Mapped[SessionAbsenceType] = mapped_column(Enum(SessionAbsenceType), nullable=False)
    status: Mapped[SessionAbsenceStatus] = mapped_column(
        Enum(SessionAbsenceStatus),
        default=SessionAbsenceStatus.PENDING_APPROVAL,
        nullable=False,
        index=True,
    )
    reason: Mapped[Optional[str]] = mapped_column(String(255))
    notes: Mapped[Optional[str]] = mapped_column(Text)
    leave_billing_category: Mapped[Optional[str]] = mapped_column(String(32))
    requested_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    reviewed_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    review_note: Mapped[Optional[str]] = mapped_column(Text)
    billing_outcome: Mapped[Optional[str]] = mapped_column(Text)
    therapist_leave_id: Mapped[Optional[int]] = mapped_column(ForeignKey("therapist_leaves.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    session = relationship("Session", foreign_keys=[session_id])
    case = relationship("Case", foreign_keys=[case_id])
    therapist = relationship("User", foreign_keys=[therapist_user_id])
    requester = relationship("User", foreign_keys=[requested_by_user_id])
    reviewer = relationship("User", foreign_keys=[reviewed_by_user_id])
