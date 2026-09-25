from __future__ import annotations

from datetime import date, datetime, time
from typing import Optional

from pydantic import BaseModel, Field


class SessionAbsenceCreate(BaseModel):
    absence_type: str
    reason: Optional[str] = None
    notes: Optional[str] = None
    leave_billing_category: Optional[str] = None
    confirm_replace_log: bool = False


class ChildAbsenceBackfillCreate(BaseModel):
    case_id: int = Field(..., ge=1)
    scheduled_date: date
    reason: Optional[str] = None
    notes: Optional[str] = None
    start_time: Optional[time] = None
    end_time: Optional[time] = None


class SessionAbsenceReview(BaseModel):
    review_note: Optional[str] = None


class SessionAbsenceRead(BaseModel):
    id: int
    session_id: int
    case_id: int
    case_code: Optional[str] = None
    child_name: Optional[str] = None
    therapist_user_id: int
    therapist_name: Optional[str] = None
    absence_type: str
    status: str
    reason: Optional[str] = None
    notes: Optional[str] = None
    leave_billing_category: Optional[str] = None
    requested_by_user_id: int
    reviewed_by_user_id: Optional[int] = None
    review_note: Optional[str] = None
    billing_outcome: Optional[str] = None
    scheduled_date: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    created_at: Optional[datetime] = None
    reviewed_at: Optional[datetime] = None
    dispute_status: Optional[str] = None
    record_type: Optional[str] = None
    leave_status: Optional[str] = None
    is_retroactive: Optional[bool] = None
    is_migration_reentry: Optional[bool] = None

    model_config = {"from_attributes": True}


class SessionAbsenceListResponse(BaseModel):
    items: list[SessionAbsenceRead] = Field(default_factory=list)
    total: Optional[int] = None
    page: Optional[int] = None
    page_size: Optional[int] = None
    counts: Optional[dict[str, int]] = None


class SessionAbsenceStatusResponse(BaseModel):
    status: str  # none | pending | approved | rejected
    message: Optional[str] = None
    absence_request: Optional[SessionAbsenceRead] = None


class TodayAbsenceSessionRead(BaseModel):
    id: int
    case_id: int
    case_code: Optional[str] = None
    child_name: Optional[str] = None
    scheduled_date: str
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    status: str
    has_daily_log: bool = False
    log_approval_status: Optional[str] = None


class TodayAbsenceSessionsResponse(BaseModel):
    items: list[TodayAbsenceSessionRead] = Field(default_factory=list)


class SessionAbsenceDuplicateResponse(BaseModel):
    status: str = "pending"
    message: str
    existing: bool = True
    absence_request: SessionAbsenceRead
