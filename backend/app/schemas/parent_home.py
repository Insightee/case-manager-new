from __future__ import annotations

from typing import Any, Optional

from datetime import date, datetime

from pydantic import BaseModel


class ParentSessionHighlight(BaseModel):
    headline: str
    summary_paragraph: Optional[str] = None
    attendance_label: str
    what_we_did: Optional[str] = None
    what_is_next: Optional[str] = None
    scheduled_date: Optional[date] = None
    therapist_name: Optional[str] = None


class ParentRecentUpdate(BaseModel):
    id: int
    case_id: int
    case_code: Optional[str] = None
    child_name: Optional[str] = None
    headline: str
    summary_paragraph: Optional[str] = None
    attendance_label: str
    what_we_did: Optional[str] = None
    what_is_next: Optional[str] = None
    scheduled_date: date
    therapist_name: Optional[str] = None
    submitted_at: Optional[datetime] = None


class ParentHomeStats(BaseModel):
    case_count: int
    unread_notifications: int
    pending_iep: int
    next_appointment: Optional[str] = None


class ParentHomeCase(BaseModel):
    id: int
    caseId: str
    childName: str
    serviceType: Optional[str] = None
    productModule: Optional[str] = None
    status: str
    therapistName: Optional[str] = None
    caseManagerName: Optional[str] = None
    latestApprovedReportMonth: Optional[str] = None
    iepStatus: str
    upcomingBooking: Optional[str] = None
    session_highlight: Optional[ParentSessionHighlight] = None


class PendingAssignmentAcceptance(BaseModel):
    assignment_id: int
    case_id: int
    case_code: str
    child_name: str
    therapist_name: Optional[str] = None
    offer_sent_at: Optional[str] = None


class ParentHomeResponse(BaseModel):
    stats: ParentHomeStats
    cases: list[ParentHomeCase]
    recent_updates: list[ParentRecentUpdate]
    upcoming_appointments: list[dict[str, Any]]
    pending_assignment_acceptance: list[PendingAssignmentAcceptance] = []
