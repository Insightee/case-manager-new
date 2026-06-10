from __future__ import annotations

from typing import Optional

from datetime import date, datetime, time

from pydantic import BaseModel, EmailStr, Field

from app.models.session import SessionMode, SessionStatus


class SessionCreate(BaseModel):
    case_id: int
    therapist_user_id: Optional[int] = None
    scheduled_date: date
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    mode: SessionMode = SessionMode.HOME
    status: SessionStatus = SessionStatus.SCHEDULED


class SessionUpdate(BaseModel):
    scheduled_date: Optional[date] = None
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    mode: Optional[SessionMode] = None
    status: Optional[SessionStatus] = None


class ManualSessionCreate(BaseModel):
    case_id: int
    scheduled_date: date
    actual_start_at: datetime
    actual_end_at: datetime
    mode: SessionMode = SessionMode.HOME


class ManualWalkInSessionCreate(BaseModel):
    client_name: str = Field(..., min_length=1, max_length=255)
    client_email: EmailStr
    child_name: str = Field(..., min_length=1, max_length=255)
    client_phone: Optional[str] = None
    scheduled_date: date
    actual_start_at: datetime
    actual_end_at: datetime
    mode: SessionMode = SessionMode.HOME
    product_module: str = "homecare"


class SessionRead(BaseModel):
    id: int
    case_id: int
    case_code: Optional[str] = None
    child_name: Optional[str] = None
    therapist_user_id: int
    scheduled_date: date
    start_time: Optional[time]
    end_time: Optional[time]
    actual_start_at: Optional[datetime] = None
    actual_end_at: Optional[datetime] = None
    edited_start_at: Optional[datetime] = None
    edited_end_at: Optional[datetime] = None
    actual_times_edit_reason: Optional[str] = None
    auto_ended: bool = False
    auto_end_reason: Optional[str] = None
    auto_end_label: Optional[str] = None
    slot_duration_minutes: Optional[int] = None
    mode: SessionMode
    status: SessionStatus
    has_daily_log: bool = False
    checkin_lat: Optional[float] = None
    checkin_lng: Optional[float] = None
    checkout_lat: Optional[float] = None
    checkout_lng: Optional[float] = None
    invite_sent: bool = False
    invite_email: Optional[str] = None
    scheduled_duration_mins: Optional[int] = None
    overage_mins: Optional[int] = None
    time_confirmation_required: bool = False
    actual_times_edited: bool = False
    duplicate_day_session: bool = False
    resumed_count: int = 0
    recommended_action: Optional[str] = None

    model_config = {"from_attributes": True}


class SessionActualTimesUpdate(BaseModel):
    actual_start_at: datetime
    actual_end_at: datetime
    edit_reason: str = Field(..., min_length=5, max_length=512)


class TherapistClientIntakeCreate(BaseModel):
    client_name: str = Field(..., min_length=1, max_length=255)
    client_email: EmailStr
    child_name: str = Field(..., min_length=1, max_length=255)
    client_phone: Optional[str] = None
    product_module: str = "homecare"


class TherapistClientIntakeResponse(BaseModel):
    case_id: int
    case_code: str
    child_name: str
    parent_email: str
    invite_sent: bool = False
    invite_url: Optional[str] = None


class ManualWalkInSessionResponse(BaseModel):
    session: SessionRead
    case_id: int
    case_code: str
    invite_url: Optional[str] = None
    invite_sent: bool = False
