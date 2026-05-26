from __future__ import annotations

from typing import Literal, Optional

from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models.visibility import VisibilityStatus


class AdminReportListItem(BaseModel):
    report_type: Literal["monthly", "observation"]
    id: int
    case_id: int
    case_code: Optional[str] = None
    child_name: Optional[str] = None
    product_module: Optional[str] = None
    therapist_user_id: int
    therapist_name: Optional[str] = None
    label: str
    status: str
    visibility_status: Optional[str] = None
    parent_review_status: Optional[str] = None
    parent_feedback: Optional[str] = None
    content_preview: Optional[str] = None
    category: Optional[str] = None
    updated_at: Optional[datetime] = None


class AdminReportReviewHistoryItem(BaseModel):
    id: int
    decision: str
    comment: Optional[str] = None
    reviewer_name: Optional[str] = None
    created_at: Optional[datetime] = None


class AdminReportDetail(BaseModel):
    report_type: Literal["monthly", "observation"]
    id: int
    case_id: int
    case_code: Optional[str] = None
    child_name: Optional[str] = None
    product_module: Optional[str] = None
    therapist_user_id: int
    therapist_name: Optional[str] = None
    label: str
    status: str
    summary: Optional[str] = None
    content: Optional[str] = None
    body_html: Optional[str] = None
    plan_next_month: Optional[str] = None
    category: Optional[str] = None
    sub_category: Optional[str] = None
    report_date: Optional[date] = None
    reviewer_comment: Optional[str] = None
    visibility_status: Optional[str] = None
    parent_review_status: Optional[str] = None
    parent_feedback: Optional[str] = None
    parent_reviewed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    review_history: list[AdminReportReviewHistoryItem] = Field(default_factory=list)


class AdminReportTypeSummary(BaseModel):
    draft: int = 0
    under_review: int = 0
    rejected: int = 0
    published: int = 0
    parent_changes_requested: int = 0


class AdminReportSummary(BaseModel):
    monthly: AdminReportTypeSummary
    observation: AdminReportTypeSummary
    queue_total: int
    iep_pending: int = 0


class CmReviewAction(BaseModel):
    comment: str
    request_changes: bool = False


class SendForReviewAction(BaseModel):
    target: Literal["therapist", "case_manager"]
    comment: str


class ReportCommentAction(BaseModel):
    comment: str


class BulkReportAction(BaseModel):
    report_type: Literal["monthly", "observation"]
    ids: list[int] = Field(min_length=1, max_length=100)
    comment: Optional[str] = None
    visibility_status: Optional[VisibilityStatus] = None


class BulkReportResult(BaseModel):
    succeeded: int
    failed: int
    errors: list[str] = Field(default_factory=list)
