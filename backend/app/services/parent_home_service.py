from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.user import User

from app.models.case import Case
from app.models.daily_log import DailyLog, LogApprovalStatus
from app.models.session import Session as TherapySession
from app.models.user import User
from app.schemas.parent_home import (
    ParentHomeCase,
    ParentHomeResponse,
    ParentHomeStats,
    ParentRecentUpdate,
    ParentSessionHighlight,
)
from app.services import notification_service, parent_service


ATTENDANCE_LABELS = {
    "PRESENT": "Attended",
    "ABSENT": "Absent",
    "LATE": "Arrived late",
    "CANCELLED": "Cancelled",
}


def _attendance_label(raw: str | None) -> str:
    if not raw:
        return "Session completed"
    key = str(raw).upper()
    return ATTENDANCE_LABELS.get(key, "Session completed")


def _headline_from_log(log: DailyLog, child_name: str | None) -> str:
    att = _attendance_label(log.attendance_status)
    if log.parent_notes and log.parent_notes.strip():
        return log.parent_notes.strip()[:120]
    if att == "Attended":
        return f"A good session{f' with {child_name}' if child_name else ''}"
    return f"{att}{f' — {child_name}' if child_name else ''}"


def _summary_paragraph(log: DailyLog) -> str | None:
    if log.parent_notes and log.parent_notes.strip():
        return log.parent_notes.strip()
    parts = []
    if log.activities_done:
        parts.append(log.activities_done.strip())
    if log.follow_ups:
        parts.append(log.follow_ups.strip())
    if parts:
        return " ".join(parts)[:500]
    return None


def parent_log_card_fields(log: DailyLog, *, case: Case | None, therapist_name: str | None) -> dict:
    child_name = case.child.full_name if case and case.child else None
    return {
        "headline": _headline_from_log(log, child_name),
        "summary_paragraph": _summary_paragraph(log),
        "attendance_label": _attendance_label(log.attendance_status),
        "what_we_did": log.activities_done,
        "what_is_next": log.follow_ups,
        "scheduled_date": log.session.scheduled_date if log.session else None,
        "therapist_name": therapist_name,
    }


def _approved_logs_for_parent(db: Session, user: User, *, limit: int | None = None) -> list[DailyLog]:
    child_ids = parent_service.child_ids_for_parent(db, user.id)
    if not child_ids:
        return []
    case_stmt = select(Case).where(Case.child_id.in_(child_ids))
    cases = {c.id: c for c in db.scalars(case_stmt).all()}
    if not cases:
        return []
    log_stmt = (
        select(DailyLog)
        .join(TherapySession)
        .where(
            TherapySession.case_id.in_(cases.keys()),
            DailyLog.submitted_at.isnot(None),
            DailyLog.visibility_status.in_(parent_service.PARENT_VISIBLE),
            DailyLog.approval_status == LogApprovalStatus.APPROVED,
        )
        .options(
            selectinload(DailyLog.session).selectinload(TherapySession.case).selectinload(Case.child),
        )
        .order_by(TherapySession.scheduled_date.desc())
    )
    if limit:
        log_stmt = log_stmt.limit(limit)
    return list(db.scalars(log_stmt).all())


def build_parent_home(db: Session, user: User) -> ParentHomeResponse:
    cases_raw = parent_service.list_parent_cases(db, user)
    unread = notification_service.unread_count(db, user.id)

    pending_iep = sum(1 for c in cases_raw if c.get("iepStatus") == "pending")
    next_appt = None
    for c in cases_raw:
        ub = c.get("upcomingBooking")
        if ub:
            next_appt = ub
            break

    logs = _approved_logs_for_parent(db, user, limit=50)
    latest_by_case: dict[int, DailyLog] = {}
    therapist_ids: set[int] = set()
    for log in logs:
        if log.session:
            therapist_ids.add(log.session.therapist_user_id)
    therapist_names: dict[int, str | None] = {}
    if therapist_ids:
        for u in db.scalars(select(User).where(User.id.in_(therapist_ids))).all():
            therapist_names[u.id] = u.full_name

    for log in logs:
        if not log.session:
            continue
        cid = log.session.case_id
        if cid not in latest_by_case:
            latest_by_case[cid] = log

    cases: list[ParentHomeCase] = []
    for c in cases_raw:
        highlight = None
        log = latest_by_case.get(c["id"])
        if log and log.session:
            case = log.session.case
            tname = therapist_names.get(log.session.therapist_user_id)
            fields = parent_log_card_fields(log, case=case, therapist_name=tname)
            highlight = ParentSessionHighlight(**fields)
        cases.append(
            ParentHomeCase(
                id=c["id"],
                caseId=c["caseId"],
                childName=c["childName"],
                serviceType=c.get("serviceType"),
                productModule=c.get("productModule"),
                status=c["status"],
                therapistName=c.get("therapistName"),
                caseManagerName=c.get("caseManagerName"),
                latestApprovedReportMonth=c.get("latestApprovedReportMonth"),
                iepStatus=c.get("iepStatus", "none"),
                upcomingBooking=c.get("upcomingBooking"),
                session_highlight=highlight,
            )
        )

    recent: list[ParentRecentUpdate] = []
    for log in logs[:3]:
        s = log.session
        if not s:
            continue
        case = s.case
        fields = parent_log_card_fields(
            log, case=case, therapist_name=therapist_names.get(s.therapist_user_id)
        )
        recent.append(
            ParentRecentUpdate(
                id=log.id,
                case_id=s.case_id,
                case_code=case.case_code if case else None,
                child_name=case.child.full_name if case and case.child else None,
                submitted_at=log.submitted_at,
                scheduled_date=s.scheduled_date,
                **{k: v for k, v in fields.items() if k != "scheduled_date"},
            )
        )

    upcoming: list[dict] = []
    today = date.today()
    for c in cases_raw:
        ub = c.get("upcomingBooking")
        if ub:
            upcoming.append(
                {
                    "caseId": c["caseId"],
                    "caseDbId": c["id"],
                    "childName": c["childName"],
                    "label": ub,
                    "therapistName": c.get("therapistName"),
                }
            )

    return ParentHomeResponse(
        stats=ParentHomeStats(
            case_count=len(cases_raw),
            unread_notifications=unread,
            pending_iep=pending_iep,
            next_appointment=next_appt,
        ),
        cases=cases,
        recent_updates=recent,
        upcoming_appointments=upcoming,
    )
