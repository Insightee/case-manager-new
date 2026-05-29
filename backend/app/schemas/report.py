from __future__ import annotations

from typing import Optional

from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models.report import ReportStatus
from app.models.visibility import VisibilityStatus


class MonthlyReportCreate(BaseModel):
    case_id: int
    month: str
    summary: Optional[str] = None
    body_html: Optional[str] = None
    plan_next_month: Optional[str] = None
    category: Optional[str] = "CLIENT_MONTHLY"
    sub_category: Optional[str] = None
    report_date: Optional[date] = None


class MonthlyReportUpdate(BaseModel):
    month: Optional[str] = None
    summary: Optional[str] = None
    body_html: Optional[str] = None
    plan_next_month: Optional[str] = None
    category: Optional[str] = None
    sub_category: Optional[str] = None
    report_date: Optional[date] = None


class MonthlyReportRead(BaseModel):
    id: int
    case_id: int
    case_code: Optional[str] = None
    child_name: Optional[str] = None
    therapist_user_id: int
    month: str
    status: ReportStatus
    summary: Optional[str]
    body_html: Optional[str] = None
    plan_next_month: Optional[str] = None
    category: Optional[str] = None
    sub_category: Optional[str] = None
    report_date: Optional[date] = None
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
    body_html: Optional[str] = None
    plan_next_month: Optional[str] = None
    category: Optional[str] = "OBSERVATION"
    sub_category: Optional[str] = None
    report_date: Optional[date] = None


class ObservationReportUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    body_html: Optional[str] = None
    plan_next_month: Optional[str] = None
    category: Optional[str] = None
    sub_category: Optional[str] = None
    report_date: Optional[date] = None


class ObservationReportRead(BaseModel):
    id: int
    case_id: int
    case_code: Optional[str] = None
    child_name: Optional[str] = None
    therapist_user_id: int
    title: str
    status: ReportStatus
    content: Optional[str] = None
    body_html: Optional[str] = None
    plan_next_month: Optional[str] = None
    category: Optional[str] = None
    sub_category: Optional[str] = None
    report_date: Optional[date] = None
    visibility_status: VisibilityStatus
    created_at: datetime

    model_config = {"from_attributes": True}


class SessionLogContextItem(BaseModel):
    log_id: int
    scheduled_date: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    attendance_status: Optional[str] = None
    approval_status: Optional[str] = None
    activities_done: Optional[str] = None
    goals_addressed: Optional[str] = None
    follow_ups: Optional[str] = None
    parent_notes: Optional[str] = None
    session_notes: Optional[str] = None


class GenerateFromLogsRequest(BaseModel):
    mode: str = Field(default="replace", pattern="^(replace|append)$")


class MissingMonthlyCaseItem(BaseModel):
    case_id: int
    case_code: str
    child_name: str
    therapist_name: Optional[str] = None
    product_module: Optional[str] = None
