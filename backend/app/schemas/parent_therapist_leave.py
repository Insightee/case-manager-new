from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel


class ParentTherapistLeaveDayRead(BaseModel):
    """Parent-safe therapist leave impact for session updates."""

    id: str
    leave_id: int
    case_id: int
    case_code: Optional[str] = None
    child_name: Optional[str] = None
    therapist_name: Optional[str] = None
    scheduled_date: date
    leave_end_date: Optional[date] = None
    reason: Optional[str] = None
    status: str
    status_label: str
