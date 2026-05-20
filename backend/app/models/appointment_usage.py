from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class CaseAppointmentUsage(Base):
    __tablename__ = "case_appointment_usage"
    __table_args__ = (UniqueConstraint("case_id", "year", "month", name="uq_case_appointment_usage_month"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    reschedules_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
