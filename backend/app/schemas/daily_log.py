from __future__ import annotations

from typing import Optional

from datetime import date, datetime

from pydantic import BaseModel

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
    attendance_status: str
    session_notes: Optional[str] = None
    activities_done: Optional[str] = None
    goals_addressed: Optional[str] = None
    observations: Optional[str] = None
    follow_ups: Optional[str] = None
    parent_notes: Optional[str] = None
    submitted_at: Optional[datetime]
    approval_status: LogApprovalStatus
    late_addition: bool = False
    late_reason: Optional[str] = None

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
    attendance_status: str
    activities_done: Optional[str] = None
    goals_addressed: Optional[str] = None
    follow_ups: Optional[str] = None
    parent_notes: Optional[str] = None
    submitted_at: Optional[datetime] = None
