from __future__ import annotations

import enum
from datetime import date, datetime
from typing import Optional

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ObservationChecklistStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class CaseClinicalProfile(Base):
    """Structured clinical snapshot for a case (filled via observation workflow)."""

    __tablename__ = "case_clinical_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), nullable=False, unique=True, index=True)
    history: Mapped[Optional[str]] = mapped_column(Text)
    diagnosis: Mapped[Optional[str]] = mapped_column(Text)
    strengths: Mapped[Optional[str]] = mapped_column(Text)
    interests: Mapped[Optional[str]] = mapped_column(Text)
    goals_summary: Mapped[Optional[str]] = mapped_column(Text)
    updated_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ObservationChecklist(Base):
    """Therapist observation intake form; CM approves and publishes parent-visible report."""

    __tablename__ = "observation_checklists"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), nullable=False, unique=True, index=True)
    therapist_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=ObservationChecklistStatus.DRAFT.value)
    section_responses_json: Mapped[Optional[str]] = mapped_column(Text)
    due_at: Mapped[Optional[date]] = mapped_column(Date)
    due_rule: Mapped[Optional[str]] = mapped_column(String(64))
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    reviewed_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    reviewer_comment: Mapped[Optional[str]] = mapped_column(Text)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    observation_report_id: Mapped[Optional[int]] = mapped_column(ForeignKey("observation_reports.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
