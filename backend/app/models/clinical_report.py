from __future__ import annotations

import enum
from datetime import date, datetime
from typing import Optional

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ClinicalReportType(str, enum.Enum):
    OBSERVATION = "observation"
    IEP = "iep"
    MONTHLY = "monthly"
    PROGRESS = "progress"
    HISTORY = "history"


class ClinicalReportStatus(str, enum.Enum):
    DRAFT = "draft"
    IN_PROGRESS = "in_progress"
    SUBMITTED_FOR_REVIEW = "submitted_for_review"
    RETURNED_FOR_CHANGES = "returned_for_changes"
    APPROVED = "approved"
    LOCKED = "locked"
    ARCHIVED = "archived"


class SectionVisibility(str, enum.Enum):
    INTERNAL_ONLY = "internal_only"
    CLINICAL_TEAM = "clinical_team"
    PARENT_VISIBLE = "parent_visible"


class SectionCompletionStatus(str, enum.Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    NEEDS_REVIEW = "needs_review"


class EvidenceSourceType(str, enum.Enum):
    SESSION_LOG = "session_log"
    GOAL = "goal"
    STRATEGY = "strategy"
    PARENT_INPUT = "parent_input"
    SCHOOL_INPUT = "school_input"
    THERAPIST_NOTE = "therapist_note"
    UPLOADED_DOCUMENT = "uploaded_document"
    OBSERVATION_CANDIDATE_GOAL = "observation_candidate_goal"
    OBSERVATION_CANDIDATE_STRATEGY = "observation_candidate_strategy"


class ReviewEventType(str, enum.Enum):
    CREATED = "created"
    EDITED = "edited"
    SUBMITTED = "submitted"
    RETURNED = "returned"
    APPROVED = "approved"
    LOCKED = "locked"
    REOPENED = "reopened"
    PARENT_SHARED = "parent_shared"


class ClinicalReport(Base):
    __tablename__ = "clinical_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), nullable=False, index=True)
    child_id: Mapped[Optional[int]] = mapped_column(ForeignKey("children.id"), nullable=True, index=True)
    report_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=ClinicalReportStatus.DRAFT.value, index=True)
    current_version_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    assigned_therapist_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    case_manager_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    due_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    returned_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    approved_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    parent_visible_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    locked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    metadata_json: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    archived_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class ClinicalReportVersion(Base):
    __tablename__ = "clinical_report_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("clinical_reports.id", ondelete="CASCADE"), nullable=False, index=True)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    snapshot_json: Mapped[Optional[str]] = mapped_column(Text)
    change_reason: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ClinicalReportSection(Base):
    __tablename__ = "clinical_report_sections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("clinical_reports.id", ondelete="CASCADE"), nullable=False, index=True)
    section_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    section_title: Mapped[str] = mapped_column(String(255), nullable=False)
    section_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    structured_data_json: Mapped[Optional[str]] = mapped_column(Text)
    narrative_text: Mapped[Optional[str]] = mapped_column(Text)
    internal_notes: Mapped[Optional[str]] = mapped_column(Text)
    completion_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=SectionCompletionStatus.NOT_STARTED.value
    )
    visibility: Mapped[str] = mapped_column(String(32), nullable=False, default=SectionVisibility.CLINICAL_TEAM.value)
    evidence_refs_json: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ClinicalReportEvidence(Base):
    __tablename__ = "clinical_report_evidence"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("clinical_reports.id", ondelete="CASCADE"), nullable=False, index=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    section_key: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    evidence_label: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    visibility: Mapped[str] = mapped_column(String(32), nullable=False, default=SectionVisibility.CLINICAL_TEAM.value)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ClinicalReportReviewEvent(Base):
    __tablename__ = "clinical_report_review_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("clinical_reports.id", ondelete="CASCADE"), nullable=False, index=True)
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    actor_role: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    comment: Mapped[Optional[str]] = mapped_column(Text)
    metadata_json: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
