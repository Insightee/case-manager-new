"""Forgot-to-log duplicate session detection."""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.case import Case
from app.models.daily_log import LogApprovalStatus
from app.models.session import Session as TherapySession
from app.models.session import SessionStatus

VOID_STATUSES = frozenset({SessionStatus.CANCELLED, SessionStatus.RESCHEDULED})

_STATUS_PRIORITY = (
    SessionStatus.IN_PROGRESS,
    SessionStatus.COMPLETED,
    SessionStatus.SCHEDULED,
    SessionStatus.CLIENT_ABSENT,
    SessionStatus.THERAPIST_LEAVE,
    SessionStatus.NO_SHOW,
)


def find_existing_session_for_date(
    db: Session,
    *,
    case_id: int,
    therapist_user_id: int,
    scheduled_date: date,
) -> TherapySession | None:
    rows = db.scalars(
        select(TherapySession)
        .where(
            TherapySession.case_id == case_id,
            TherapySession.therapist_user_id == therapist_user_id,
            TherapySession.scheduled_date == scheduled_date,
            TherapySession.status.notin_(tuple(VOID_STATUSES)),
        )
        .options(selectinload(TherapySession.daily_log), selectinload(TherapySession.case).selectinload(Case.child))
        .order_by(TherapySession.id.asc())
    ).all()
    if not rows:
        return None
    if len(rows) == 1:
        return rows[0]

    def rank(session: TherapySession) -> int:
        try:
            return _STATUS_PRIORITY.index(session.status)
        except ValueError:
            return len(_STATUS_PRIORITY)

    return min(rows, key=rank)


def _log_status(session: TherapySession) -> str:
    log = session.daily_log
    if not log:
        if session.status == SessionStatus.COMPLETED:
            return "incomplete"
        return "not_started"
    if log.approval_status == LogApprovalStatus.APPROVED:
        return "approved"
    if log.approval_status == LogApprovalStatus.PENDING:
        return "submitted"
    if log.approval_status == LogApprovalStatus.REJECTED:
        return "incomplete"
    return "incomplete"


def _recommended_action(session: TherapySession, log_status: str) -> str:
    if session.status == SessionStatus.IN_PROGRESS:
        return "resume_session"
    if log_status == "approved":
        return "view_log"
    if log_status == "submitted":
        return "view_log"
    return "edit_log"


def build_existing_session_conflict(db: Session, session: TherapySession) -> dict:
    from app.services import session_absence_service as absence_svc

    block = absence_svc.get_child_absence_block(db, session.id, for_manual_log=True)
    case = session.case
    child_name = case.child.full_name if case and case.child else (case.case_code if case else None)
    if block:
        return {
            "code": block["code"],
            "existing_session_id": session.id,
            "daily_log_id": None,
            "has_daily_log": False,
            "child_name": child_name,
            "case_id": session.case_id,
            "case_code": case.case_code if case else None,
            "scheduled_date": session.scheduled_date.isoformat(),
            "start_time": str(session.start_time) if session.start_time else None,
            "end_time": str(session.end_time) if session.end_time else None,
            "actual_start_at": session.actual_start_at.isoformat() if session.actual_start_at else None,
            "actual_end_at": session.actual_end_at.isoformat() if session.actual_end_at else None,
            "session_status": session.status.value,
            "log_status": None,
            "recommended_action": "blocked_absence",
            "message": block["message"],
        }

    log_status = _log_status(session)
    recommended_action = _recommended_action(session, log_status)
    daily_log = session.daily_log
    return {
        "code": "EXISTING_SESSION_FOR_DATE",
        "existing_session_id": session.id,
        "daily_log_id": daily_log.id if daily_log else None,
        "has_daily_log": daily_log is not None,
        "child_name": child_name,
        "case_id": session.case_id,
        "case_code": case.case_code if case else None,
        "scheduled_date": session.scheduled_date.isoformat(),
        "start_time": str(session.start_time) if session.start_time else None,
        "end_time": str(session.end_time) if session.end_time else None,
        "actual_start_at": session.actual_start_at.isoformat() if session.actual_start_at else None,
        "actual_end_at": session.actual_end_at.isoformat() if session.actual_end_at else None,
        "session_status": session.status.value,
        "log_status": log_status,
        "recommended_action": recommended_action,
        "message": "A session already exists for this child on this date. Please update the existing session log instead of creating another one.",
    }
