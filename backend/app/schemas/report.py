from __future__ import annotations

from typing import Optional

from datetime import datetime

from pydantic import BaseModel

from app.models.report import ReportStatus
from app.models.visibility import VisibilityStatus


class MonthlyReportCreate(BaseModel):
    case_id: int
    month: str
    summary: Optional[str] = None


class MonthlyReportUpdate(BaseModel):
    month: Optional[str] = None
    summary: Optional[str] = None


class MonthlyReportRead(BaseModel):
    id: int
    case_id: int
    case_code: Optional[str] = None
    child_name: Optional[str] = None
    therapist_user_id: int
    month: str
    status: ReportStatus
    summary: Optional[str]
    reviewer_comment: Optional[str]
    visibility_status: VisibilityStatus
    parent_review_status: Optional[str] = None
    parent_feedback: Optional[str] = None
    parent_reviewed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ReviewAction(BaseModel):
    comment: Optional[str] = None
    visibility_status: Optional[VisibilityStatus] = None


class ObservationReportCreate(BaseModel):
    case_id: int
    title: str
    content: Optional[str] = None


class ObservationReportUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None


class ObservationReportRead(BaseModel):
    id: int
    case_id: int
    case_code: Optional[str] = None
    child_name: Optional[str] = None
    therapist_user_id: int
    title: str
    status: ReportStatus
    content: Optional[str] = None
    visibility_status: VisibilityStatus
    created_at: datetime

    model_config = {"from_attributes": True}
