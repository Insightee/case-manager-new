from __future__ import annotations

import enum
from datetime import date, datetime
from typing import Optional

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Integer, JSON, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

TRANSITION_DEFAULT_DAY_COUNT = 3
TRANSITION_FULL_DAY_PAY_INR = 500
TRANSITION_HALF_DAY_PAY_INR = 350


class CaseTherapistTransitionStatus(str, enum.Enum):
    SCHEDULED = "SCHEDULED"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class CaseTherapistTransition(Base):
    __tablename__ = "case_therapist_transitions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), nullable=False, index=True)
    case_service_id: Mapped[int] = mapped_column(ForeignKey("case_services.id"), nullable=False, index=True)
    outgoing_therapist_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    incoming_therapist_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    outgoing_assignment_id: Mapped[int] = mapped_column(ForeignKey("case_assignments.id"), nullable=False)
    incoming_assignment_id: Mapped[int] = mapped_column(ForeignKey("case_assignments.id"), nullable=False)
    transition_dates: Mapped[list] = mapped_column(JSON, nullable=False)
    status: Mapped[CaseTherapistTransitionStatus] = mapped_column(
        Enum(CaseTherapistTransitionStatus),
        nullable=False,
        default=CaseTherapistTransitionStatus.SCHEDULED,
        index=True,
    )
    pending_billing_update: Mapped[dict] = mapped_column(JSON, nullable=False)
    full_day_pay_inr: Mapped[float] = mapped_column(
        Numeric(12, 2), nullable=False, default=TRANSITION_FULL_DAY_PAY_INR
    )
    half_day_pay_inr: Mapped[float] = mapped_column(
        Numeric(12, 2), nullable=False, default=TRANSITION_HALF_DAY_PAY_INR
    )
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    case = relationship("Case", back_populates="therapist_transitions")
