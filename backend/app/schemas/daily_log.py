from __future__ import annotations

from typing import Optional

from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models.daily_log import AttendanceStatus, LogApprovalStatus


class DailyLogCreate(BaseModel):
    session_id: int
    attendance_status: AttendanceStatus
    session_notes: Optional[str] = None
    activities_done: Optional[str] = None
    goals_addressed: Optional[str] = None
    observations: Optional[str] = None
    follow_ups: Optional[str] = None
    parent_notes: Optional[str] = None
    late_reason: Optional[str] = None


class DailyLogUpdate(BaseModel):
    attendance_status: Optional[AttendanceStatus] = None
    session_notes: Optional[str] = None
    activities_done: Optional[str] = None
    goals_addressed: Optional[str] = None
    observations: Optional[str] = None
    follow_ups: Optional[str] = None
    parent_notes: Optional[str] = None
    late_reason: Optional[str] = None


class DailyLogRead(BaseModel):
    id: int
    session_id: int
    case_id: Optional[int] = None
    case_code: Optional[str] = None
    child_name: Optional[str] = None
    scheduled_date: Optional[date] = None
    actual_start_at: Optional[datetime] = None
    actual_end_at: Optional[datetime] = None
    edited_start_at: Optional[datetime] = None
    edited_end_at: Optional[datetime] = None
    actual_times_edited: bool = False
    actual_times_edit_reason: Optional[str] = None
    duplicate_day_session: bool = False
    status_label: Optional[str] = None
    attendance_status: str
    session_notes: Optional[str] = None
    activities_done: Optional[str] = None
    goals_addressed: Optional[str] = None
    observations: Optional[str] = None
    follow_ups: Optional[str] = None
    parent_notes: Optional[str] = None
    submitted_at: Optional[datetime] = None
    approval_status: LogApprovalStatus
    late_addition: bool = False
    late_reason: Optional[str] = None
    review_note: Optional[str] = None
    resubmitted_at: Optional[datetime] = None
    can_edit: bool = False
    can_resubmit: bool = False
    editable_until: Optional[datetime] = None
    absence_reason: Optional[str] = None
    dispute_status: Optional[str] = None

    model_config = {"from_attributes": True}


class DailyLogFinanceRead(BaseModel):
    id: int
    session_id: int
    case_id: Optional[int] = None
    attendance_status: str
    activities_done: Optional[str] = None
    submitted_at: Optional[datetime]
    approval_status: LogApprovalStatus
    late_addition: bool = False
    absence_reason: Optional[str] = None
    dispute_status: Optional[str] = None

    model_config = {"from_attributes": True}


class ParentSessionLogRead(BaseModel):
    id: int
    case_id: int
    case_code: Optional[str] = None
    child_name: Optional[str] = None
    therapist_name: Optional[str] = None
    scheduled_date: date
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    actual_start_at: Optional[datetime] = None
    actual_end_at: Optional[datetime] = None
    clock_start_at: Optional[datetime] = None
    clock_end_at: Optional[datetime] = None
    edited_start_at: Optional[datetime] = None
    edited_end_at: Optional[datetime] = None
    actual_times_edited: bool = False
    attendance_status: str
    activities_done: Optional[str] = None
    goals_addressed: Optional[str] = None
    follow_ups: Optional[str] = None
    parent_notes: Optional[str] = None
    parent_session_rating: Optional[int] = None
    parent_feedback: Optional[str] = None
    parent_feedback_at: Optional[datetime] = None
    parent_feedback_public: bool = False
    submitted_at: Optional[datetime] = None
    headline: Optional[str] = None
    summary_paragraph: Optional[str] = None
    attendance_label: Optional[str] = None
    what_we_did: Optional[str] = None
    what_is_next: Optional[str] = None
    absence_reason: Optional[str] = None
    dispute_status: Optional[str] = None
    parent_display_status: Optional[str] = None
    can_parent_comment: bool = True
    comments: Optional[list[LogCommentRead]] = None


class ParentSessionFeedbackUpdate(BaseModel):
    rating: Optional[int] = Field(default=None, ge=1, le=5)
    feedback: Optional[str] = Field(default=None, max_length=2000)
    share_publicly: Optional[bool] = None


class LogCommentRead(BaseModel):
    id: int
    body: str
    author_name: Optional[str] = None
    author_role: Optional[str] = None
    visibility: Optional[str] = None
    status: Optional[str] = None
    created_at: Optional[datetime] = None


class LogCommentCreate(BaseModel):
    body: str = Field(..., min_length=1)
    visibility: Optional[str] = "parent_team"
