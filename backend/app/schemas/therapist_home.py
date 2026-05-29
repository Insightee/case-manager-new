from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel

from app.schemas.session import SessionRead


class TherapistCaseBoardRow(BaseModel):
    id: int
    caseId: str
    child: str
    service: Optional[str] = None
    productModule: Optional[str] = None
    stage: str
    badgeVariant: str
    nextDue: str
    nextBooking: Optional[dict] = None
    critical: bool = False
    needsLogCount: int = 0
    upcomingCount: int = 0
    status: str
    mapsUrl: Optional[str] = None
    serviceAddress: Optional[Any] = None
    borderAccent: str = "blue"
    showSubmitReport: bool = False
    reportStatus: Optional[str] = None
    caseManagerName: Optional[str] = None
    caseManagerEmail: Optional[str] = None
    parentSignupPending: bool = False


class TherapistCaseBoardSection(BaseModel):
    id: str
    title: str
    tone: str
    count: int
    cases: list[TherapistCaseBoardRow]


class TherapistCaseBoardStat(BaseModel):
    id: str
    label: str
    value: int
    variant: str


class SchedulePreviewItem(BaseModel):
    kind: str
    key: str
    sessionId: Optional[int] = None
    slotId: Optional[int] = None
    meetingId: Optional[int] = None
    caseId: Optional[int] = None
    childName: Optional[str] = None
    caseCode: Optional[str] = None
    date: str
    startTime: str
    endTime: str
    mode: Optional[str] = None
    bookingSource: Optional[str] = None
    subtitle: str


class TherapistHomeStats(BaseModel):
    case_count: int
    needs_log: int
    pending_logs: int
    draft_reports: int
    under_review_reports: int
    active_session_id: Optional[int] = None


class TherapistPendingAssignment(BaseModel):
    assignment_id: int
    case_id: int
    case_code: str
    child_name: str
    parent_accepted: bool = False
    offer_sent_at: Optional[str] = None


class TherapistHomeResponse(BaseModel):
    greeting_context: Optional[str] = None
    stats: TherapistHomeStats
    active_session: Optional[SessionRead] = None
    upcoming_sessions: list[SessionRead]
    needs_log_sessions: list[SessionRead]
    cases_board: dict
    schedule_preview: list[SchedulePreviewItem]
    pending_assignment_acceptance: list[TherapistPendingAssignment] = []


class TherapistSessionsWorkspaceResponse(BaseModel):
    upcoming: list[SessionRead]
    active_session: Optional[SessionRead] = None
    needs_log: list[SessionRead]
    booked_slots: list[dict]


class TherapistReportsPipelineResponse(BaseModel):
    attention: list[dict]
    in_progress: list[dict]
    published: list[dict]
    pipeline: dict
    month_label: str
