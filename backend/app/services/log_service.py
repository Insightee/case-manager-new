from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

LOG_EDIT_WINDOW = timedelta(hours=24)

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.case import Case
from app.models.daily_log import AttendanceStatus, DailyLog, LogApprovalStatus
from app.models.session import Session as TherapySession
from app.models.session import SessionStatus
from app.models.visibility import VisibilityStatus
from app.core.timezone import ensure_utc_aware, today_ist


def _normalize_attendance(value: str | AttendanceStatus) -> str:
    if isinstance(value, AttendanceStatus):
        return value.value
    raw = (value or "").strip().upper()
    legacy = {"PRESENT": AttendanceStatus.PRESENT, "ABSENT": AttendanceStatus.ABSENT, "LATE": AttendanceStatus.LATE, "PARTIAL": AttendanceStatus.PARTIAL}
    if raw in legacy:
        return legacy[raw].value
    if raw == "PRESENT" or raw == "present":
        return AttendanceStatus.PRESENT.value
    return raw or AttendanceStatus.PRESENT.value


def log_editable_until(log: DailyLog) -> datetime | None:
    if log.approval_status != LogApprovalStatus.PENDING or not log.submitted_at:
        return None
    submitted = log.submitted_at
    if submitted.tzinfo is None:
        submitted = submitted.replace(tzinfo=timezone.utc)
    return submitted + LOG_EDIT_WINDOW


def is_log_editable(log: DailyLog) -> bool:
    until = log_editable_until(log)
    if until is None:
        return False
    return datetime.now(timezone.utc) <= until


def get_log(db: Session, log_id: int) -> DailyLog | None:
    return db.scalars(
        select(DailyLog).where(DailyLog.id == log_id).options(selectinload(DailyLog.session))
    ).first()


def list_logs(
    db: Session,
    *,
    therapist_user_id: int | None = None,
    case_id: int | None = None,
    month: str | None = None,
    product_module: str | None = None,
) -> list[DailyLog]:
    stmt = select(DailyLog).join(TherapySession).options(
        selectinload(DailyLog.session).selectinload(TherapySession.case)
    )
    if therapist_user_id:
        stmt = stmt.where(TherapySession.therapist_user_id == therapist_user_id)
    if case_id:
        stmt = stmt.where(TherapySession.case_id == case_id)
    if product_module:
        stmt = stmt.join(Case, TherapySession.case_id == Case.id).where(Case.product_module == product_module)
    logs = list(db.scalars(stmt).all())
    if month:
        logs = [l for l in logs if l.session and l.session.scheduled_date.strftime("%b %Y") == month]
    return logs


def create_daily_log(db: Session, **kwargs) -> DailyLog:
    session = db.get(TherapySession, kwargs["session_id"])
    if not session:
        raise ValueError("Session not found")
    if session.status != SessionStatus.COMPLETED:
        raise ValueError("End the session before submitting a log")
    existing = db.scalars(select(DailyLog).where(DailyLog.session_id == kwargs["session_id"])).first()
    if existing:
        raise ValueError("Daily log already exists for this session")

    late = session.scheduled_date < today_ist()
    late_reason = kwargs.get("late_reason")
    if late and not (late_reason and str(late_reason).strip()):
        raise ValueError("Late reason is required for sessions from past days")

    attendance = _normalize_attendance(kwargs.get("attendance_status", AttendanceStatus.PRESENT))
    log = DailyLog(
        session_id=kwargs["session_id"],
        attendance_status=attendance,
        session_notes=kwargs.get("session_notes"),
        activities_done=kwargs.get("activities_done"),
        goals_addressed=kwargs.get("goals_addressed"),
        observations=kwargs.get("observations"),
        follow_ups=kwargs.get("follow_ups"),
        parent_notes=kwargs.get("parent_notes"),
        submitted_at=datetime.now(timezone.utc),
        approval_status=LogApprovalStatus.PENDING,
        late_addition=late,
        late_reason=late_reason.strip() if late and late_reason else None,
        visibility_status=VisibilityStatus.APPROVED_FOR_PARENT,
    )
    db.add(log)
    db.flush()
    return log


def update_daily_log(db: Session, log: DailyLog, therapist_user_id: int, **kwargs) -> DailyLog:
    session = log.session or db.get(TherapySession, log.session_id)
    if not session or session.therapist_user_id != therapist_user_id:
        raise ValueError("Access denied")
    if log.approval_status != LogApprovalStatus.PENDING:
        raise ValueError("Only pending logs can be edited")
    if not is_log_editable(log):
        raise ValueError("Logs can only be edited within 24 hours of submission")

    for field in ("session_notes", "activities_done", "goals_addressed", "observations", "follow_ups", "parent_notes", "late_reason"):
        if field in kwargs and kwargs[field] is not None:
            setattr(log, field, kwargs[field])
    if kwargs.get("attendance_status") is not None:
        log.attendance_status = _normalize_attendance(kwargs["attendance_status"])
    db.flush()
    return log


def log_to_read(log: DailyLog, include_clinical: bool = True) -> dict:
    session = log.session
    case = session.case if session and getattr(session, "case", None) else None
    data = {
        "id": log.id,
        "session_id": log.session_id,
        "case_id": session.case_id if session else None,
        "case_code": case.case_code if case else (session.case.case_code if session and getattr(session, "case", None) else None),
        "attendance_status": log.attendance_status,
        "activities_done": log.activities_done,
        "goals_addressed": log.goals_addressed,
        "follow_ups": log.follow_ups,
        "submitted_at": log.submitted_at,
        "approval_status": log.approval_status,
        "late_addition": bool(log.late_addition),
        "late_reason": log.late_reason,
        "review_note": log.review_note,
        "can_edit": is_log_editable(log),
        "editable_until": log_editable_until(log),
    }
    if session:
        data["scheduled_date"] = session.scheduled_date
        data["actual_start_at"] = ensure_utc_aware(session.actual_start_at)
        data["actual_end_at"] = ensure_utc_aware(session.actual_end_at)
        if case and getattr(case, "child", None):
            data["child_name"] = case.child.full_name
    if session and not data.get("case_code") and getattr(session, "case", None):
        data["case_code"] = session.case.case_code
    if include_clinical:
        data["session_notes"] = log.session_notes
        data["observations"] = log.observations
        data["parent_notes"] = log.parent_notes
    return data
