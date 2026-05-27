from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.models.daily_log import AttendanceStatus, LogApprovalStatus
from app.schemas.daily_log import DailyLogCreate


class TherapistMyCaseItem(BaseModel):
    case_id: int
    case_code: str
    external_case_ref: Optional[str] = None
    child_id: int
    child_name: Optional[str] = None
    product_module: str
    service_type: str
    status: str
    has_active_session: bool = False
    last_log_status: Optional[str] = None


class TherapistMyCasesResponse(BaseModel):
    items: list[TherapistMyCaseItem]
    total: int


class SessionLogCreate(DailyLogCreate):
    """Therapist portal alias for daily log create."""


class SessionLogRead(BaseModel):
    id: int
    session_id: int
    case_id: Optional[int] = None
    case_code: Optional[str] = None
    external_case_ref: Optional[str] = None
    child_name: Optional[str] = None
    therapist_user_id: Optional[int] = None
    therapist_name: Optional[str] = None
    scheduled_date: Optional[date] = None
    attendance_status: str
    session_notes: Optional[str] = None
    activities_done: Optional[str] = None
    goals_addressed: Optional[str] = None
    observations: Optional[str] = None
    follow_ups: Optional[str] = None
    parent_notes: Optional[str] = None
    submitted_at: Optional[datetime] = None
    parent_notified_at: Optional[datetime] = None
    approval_status: LogApprovalStatus
    late_addition: bool = False
    late_reason: Optional[str] = None
    review_note: Optional[str] = None
    can_edit: bool = False
    editable_until: Optional[datetime] = None
    status: Optional[str] = Field(None, description="Admin filter label: missing|pending|approved")


class AdminSessionLogListResponse(BaseModel):
    items: list[SessionLogRead]
    total: int
    page: int
    page_size: int
    pages: int
