from __future__ import annotations

import enum
from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class CaseDocumentCategory(str, enum.Enum):
    OBSERVATION_REPORT = "OBSERVATION_REPORT"
    CASE_MANAGER_MEETING_REPORT = "CASE_MANAGER_MEETING_REPORT"
    CLIENT_MONTHLY_REPORT = "CLIENT_MONTHLY_REPORT"
    MONTHLY_PROGRESS_REPORT = "MONTHLY_PROGRESS_REPORT"
    IEP_PLAN = "IEP_PLAN"
    INCIDENT_REPORT = "INCIDENT_REPORT"
    TERMINATION_PROGRESS_REPORT = "TERMINATION_PROGRESS_REPORT"
    ANNUAL_PROGRESS_REPORT = "ANNUAL_PROGRESS_REPORT"
    OTHER = "OTHER"


class CaseDocumentStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    SUPERVISOR_REVIEW = "SUPERVISOR_REVIEW"
    CHANGES_REQUESTED = "CHANGES_REQUESTED"
    CLIENT_REVIEW = "CLIENT_REVIEW"
    APPROVED = "APPROVED"
    ARCHIVED = "ARCHIVED"


class CaseDocumentVisibility(str, enum.Enum):
    INTERNAL_ONLY = "INTERNAL_ONLY"
    CLIENT_VISIBLE_AFTER_APPROVAL = "CLIENT_VISIBLE_AFTER_APPROVAL"
    CLIENT_VISIBLE = "CLIENT_VISIBLE"


class CaseDocumentSourceType(str, enum.Enum):
    UPLOAD = "UPLOAD"
    EXTERNAL_LINK = "EXTERNAL_LINK"
    NATIVE_HTML = "NATIVE_HTML"


class ExternalLinkProvider(str, enum.Enum):
    GOOGLE_DOCS = "GOOGLE_DOCS"
    GOOGLE_DRIVE = "GOOGLE_DRIVE"
    OTHER = "OTHER"


class CaseDocumentParentReviewStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    CHANGES_REQUESTED = "CHANGES_REQUESTED"


CLINICAL_CATEGORIES = frozenset(
    {
        CaseDocumentCategory.OBSERVATION_REPORT.value,
        CaseDocumentCategory.CASE_MANAGER_MEETING_REPORT.value,
        CaseDocumentCategory.CLIENT_MONTHLY_REPORT.value,
        CaseDocumentCategory.MONTHLY_PROGRESS_REPORT.value,
        CaseDocumentCategory.IEP_PLAN.value,
        CaseDocumentCategory.INCIDENT_REPORT.value,
        CaseDocumentCategory.TERMINATION_PROGRESS_REPORT.value,
        CaseDocumentCategory.ANNUAL_PROGRESS_REPORT.value,
        CaseDocumentCategory.OTHER.value,
    }
)


class CaseDocument(Base):
    __tablename__ = "case_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), nullable=False, index=True)
    child_id: Mapped[int] = mapped_column(ForeignKey("children.id"), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(48), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    report_month: Mapped[Optional[str]] = mapped_column(String(32))
    report_date: Mapped[Optional[date]] = mapped_column(Date)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=CaseDocumentStatus.DRAFT.value, index=True
    )
    visibility: Mapped[str] = mapped_column(
        String(48),
        nullable=False,
        default=CaseDocumentVisibility.INTERNAL_ONLY.value,
        index=True,
    )
    submitted_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    reviewer_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    parent_review_status: Mapped[Optional[str]] = mapped_column(String(32))
    parent_feedback: Mapped[Optional[str]] = mapped_column(Text)
    parent_acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    current_version_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    legacy_entity_type: Mapped[Optional[str]] = mapped_column(String(32))
    legacy_entity_id: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    versions: Mapped[list["CaseDocumentVersion"]] = relationship(
        "CaseDocumentVersion",
        back_populates="document",
        foreign_keys="CaseDocumentVersion.case_document_id",
        cascade="all, delete-orphan",
    )
    workflow_events: Mapped[list["CaseDocumentWorkflowEvent"]] = relationship(
        "CaseDocumentWorkflowEvent",
        back_populates="document",
        cascade="all, delete-orphan",
    )


class CaseDocumentVersion(Base):
    __tablename__ = "case_document_versions"
    __table_args__ = (
        UniqueConstraint("case_document_id", "version_number", name="uq_case_document_version"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_document_id: Mapped[int] = mapped_column(
        ForeignKey("case_documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    source_type: Mapped[str] = mapped_column(String(16), nullable=False)
    file_name: Mapped[Optional[str]] = mapped_column(String(255))
    storage_key: Mapped[Optional[str]] = mapped_column(String(512))
    mime_type: Mapped[Optional[str]] = mapped_column(String(128))
    size_bytes: Mapped[Optional[int]] = mapped_column(Integer)
    external_provider: Mapped[Optional[str]] = mapped_column(String(32))
    external_url: Mapped[Optional[str]] = mapped_column(String(2048))
    external_file_id: Mapped[Optional[str]] = mapped_column(String(128))
    uploaded_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    document: Mapped["CaseDocument"] = relationship(
        "CaseDocument",
        back_populates="versions",
        foreign_keys=[case_document_id],
    )


class CaseDocumentWorkflowEvent(Base):
    __tablename__ = "case_document_workflow_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_document_id: Mapped[int] = mapped_column(
        ForeignKey("case_documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    from_status: Mapped[Optional[str]] = mapped_column(String(32))
    to_status: Mapped[Optional[str]] = mapped_column(String(32))
    actor_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    comment: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    document: Mapped["CaseDocument"] = relationship("CaseDocument", back_populates="workflow_events")
