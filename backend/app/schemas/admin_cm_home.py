from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class CmCaseloadRow(BaseModel):
    id: int
    case_code: str
    child_name: Optional[str] = None
    service_type: str
    product_module: str
    status: str
    therapist_name: Optional[str] = None
    pipeline_column: Optional[str] = None
    next_action: Optional[str] = None
    open_reports: int = 0
    missing_logs: int = 0
    open_tickets: int = 0
    open_incidents: int = 0
    href: str


class CmCaseloadSummary(BaseModel):
    total: int = 0
    active: int = 0
    pending_allotment: int = 0
    needs_action: int = 0
    suspended: int = 0


class CmWorkbenchSection(BaseModel):
    count: int = 0
    items: list[dict[str, Any]] = Field(default_factory=list)


class AdminCmHomeResponse(BaseModel):
    role: str = "CASE_MANAGER"
    landing_route: str = "/admin/cm"
    caseload_summary: CmCaseloadSummary
    caseload: list[CmCaseloadRow]
    sections: dict[str, CmWorkbenchSection]
    quick_actions: list[dict[str, str]]


class CmLogReviewSessionSummary(BaseModel):
    id: int
    status: str
    scheduled_date: Optional[str] = None
    actual_start_at: Optional[str] = None
    actual_end_at: Optional[str] = None
    edited_start_at: Optional[str] = None
    edited_end_at: Optional[str] = None
    actual_times_edited: bool = False
    actual_times_edit_reason: Optional[str] = None
    duplicate_day_session: bool = False
    therapist_user_id: Optional[int] = None


class CmLogReviewLogRow(BaseModel):
    id: int
    session_id: int
    transition_id: Optional[int] = None
    transition_day_id: Optional[int] = None
    is_transition_log: bool = False
    case_id: Optional[int] = None
    case_code: Optional[str] = None
    child_name: Optional[str] = None
    approval_status: str
    submitted_at: Optional[datetime] = None
    resubmitted_at: Optional[datetime] = None
    scheduled_date: Optional[date] = None
    session_notes: Optional[str] = None
    observations: Optional[str] = None
    activities_done: Optional[str] = None
    goals_addressed: Optional[str] = None
    follow_ups: Optional[str] = None
    parent_notes: Optional[str] = None
    late_addition: bool = False
    late_reason: Optional[str] = None
    status_label: Optional[str] = None
    comment_count: int = 0
    open_parent_comment_count: int = 0
    session: CmLogReviewSessionSummary


class CmLogReviewCaseRow(BaseModel):
    case_id: int
    case_code: str
    child_name: Optional[str] = None
    service_type: str
    product_module: str
    therapist_name: Optional[str] = None
    status: str
    pending_count: int = 0
    logs: list[CmLogReviewLogRow] = Field(default_factory=list)


class CmLogReviewQueueResponse(BaseModel):
    total_pending: int = 0
    cases: list[CmLogReviewCaseRow] = Field(default_factory=list)
