from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class SessionAbsenceCreate(BaseModel):
    absence_type: str
    reason: Optional[str] = None
    notes: Optional[str] = None
    leave_billing_category: Optional[str] = None


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

    model_config = {"from_attributes": True}


class SessionAbsenceListResponse(BaseModel):
    items: list[SessionAbsenceRead] = Field(default_factory=list)


class SessionAbsenceStatusResponse(BaseModel):
    status: str  # none | pending | approved | rejected
    message: Optional[str] = None
    absence_request: Optional[SessionAbsenceRead] = None


class SessionAbsenceDuplicateResponse(BaseModel):
    status: str = "pending"
    message: str
    existing: bool = True
    absence_request: SessionAbsenceRead
