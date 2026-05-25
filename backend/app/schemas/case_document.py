from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field


class CaseDocumentVersionRead(BaseModel):
    id: int
    version_number: int
    source_type: str
    file_name: Optional[str] = None
    mime_type: Optional[str] = None
    size_bytes: Optional[int] = None
    external_provider: Optional[str] = None
    external_url: Optional[str] = None
    external_file_id: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class CaseDocumentListItem(BaseModel):
    id: int
    case_id: int
    child_id: int
    category: str
    title: str
    report_month: Optional[str] = None
    report_date: Optional[date] = None
    status: str
    visibility: str
    submitted_by_user_id: int
    parent_review_status: Optional[str] = None
    current_version: Optional[CaseDocumentVersionRead] = None
    allowed_actions: list[str] = Field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class CaseDocumentDetail(CaseDocumentListItem):
    parent_feedback: Optional[str] = None
    parent_acknowledged_at: Optional[datetime] = None
    reviewer_user_id: Optional[int] = None
    versions: list[CaseDocumentVersionRead] = Field(default_factory=list)


class CaseDocumentCreateJson(BaseModel):
    category: str
    title: str
    report_month: Optional[str] = None
    report_date: Optional[date] = None
    source_type: str
    external_url: Optional[str] = None
    external_provider: Optional[str] = None


class CaseDocumentPatch(BaseModel):
    title: Optional[str] = None
    category: Optional[str] = None
    report_month: Optional[str] = None
    report_date: Optional[date] = None


class CaseDocumentCommentCreate(BaseModel):
    body: str
    comment_type: str = "GENERAL"


class CaseDocumentCommentRead(BaseModel):
    id: int
    author_user_id: int
    comment_type: str
    body: str
    created_at: Optional[datetime] = None


class WorkflowPayload(BaseModel):
    comment: Optional[str] = None
    visibility: Optional[str] = None


class ParentFeedbackPayload(BaseModel):
    message: str
