from __future__ import annotations

from typing import Optional

import enum
from datetime import datetime

from datetime import date

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.visibility import VisibilityStatus


class ReportStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    UNDER_REVIEW = "UNDER_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    PUBLISHED = "PUBLISHED"


class ParentReviewStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    CHANGES_REQUESTED = "CHANGES_REQUESTED"


class ReportCategory(str, enum.Enum):
    CLIENT_MONTHLY = "CLIENT_MONTHLY"
    OBSERVATION = "OBSERVATION"
    CM_MEETING = "CM_MEETING"
    IEP_PLAN = "IEP_PLAN"
    INCIDENT_DOCUMENT = "INCIDENT_DOCUMENT"
    PROGRESS = "PROGRESS"


class MonthlyReport(Base):
    __tablename__ = "monthly_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), nullable=False, index=True)
    therapist_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    month: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[ReportStatus] = mapped_column(Enum(ReportStatus), default=ReportStatus.DRAFT)
    summary: Mapped[Optional[str ]] = mapped_column(Text)
    body_html: Mapped[Optional[str]] = mapped_column(Text)
    plan_next_month: Mapped[Optional[str]] = mapped_column(Text)
    category: Mapped[Optional[str]] = mapped_column(String(32), default=ReportCategory.CLIENT_MONTHLY.value)
    sub_category: Mapped[Optional[str]] = mapped_column(String(32))
    report_date: Mapped[Optional[date]] = mapped_column(Date)
    reviewer_comment: Mapped[Optional[str ]] = mapped_column(Text)
    visibility_status: Mapped[VisibilityStatus] = mapped_column(Enum(VisibilityStatus), default=VisibilityStatus.INTERNAL_ONLY)
    parent_review_status: Mapped[Optional[str]] = mapped_column(String(32))
    parent_feedback: Mapped[Optional[str]] = mapped_column(Text)
    parent_reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ObservationReport(Base):
    __tablename__ = "observation_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), nullable=False, index=True)
    therapist_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[Optional[str ]] = mapped_column(Text)
    body_html: Mapped[Optional[str]] = mapped_column(Text)
    plan_next_month: Mapped[Optional[str]] = mapped_column(Text)
    category: Mapped[Optional[str]] = mapped_column(String(32), default=ReportCategory.OBSERVATION.value)
    sub_category: Mapped[Optional[str]] = mapped_column(String(32))
    report_date: Mapped[Optional[date]] = mapped_column(Date)
    status: Mapped[ReportStatus] = mapped_column(Enum(ReportStatus), default=ReportStatus.DRAFT)
    visibility_status: Mapped[VisibilityStatus] = mapped_column(Enum(VisibilityStatus), default=VisibilityStatus.INTERNAL_ONLY)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
