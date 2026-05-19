from __future__ import annotations

from typing import Optional

from datetime import date, datetime, time

from pydantic import BaseModel, Field

from app.models.session import SessionMode, SessionStatus


class SessionCreate(BaseModel):
    case_id: int
    therapist_user_id: int
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
    auto_ended: bool = False
    mode: SessionMode
    status: SessionStatus
    has_daily_log: bool = False

    model_config = {"from_attributes": True}
