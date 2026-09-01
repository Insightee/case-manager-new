"""Detect past/today sessions that still need a disposition for billing.

An unresolved day is a scheduled or cancelled session (past or today) with:
- no pending/approved daily log,
- no pending/approved child absence,
- no pending/approved therapist leave covering the date.

Used by invoice preview (Needs attention lines), leave-submit gates, and
invoice-submit gates. Does not invent pay — only surfaces the hole.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.timezone import today_ist
from app.models.case import Case
from app.models.daily_log import DailyLog, LogApprovalStatus
from app.models.leave import LeaveStatus, TherapistLeave
from app.models.session import Session as TherapySession
from app.models.session import SessionStatus
from app.models.session_absence import SessionAbsenceRequest, SessionAbsenceStatus, SessionAbsenceType
from app.services import therapist_invoice_labels as labels

REASON_SESSION_CANCELLED = "session_cancelled"
REASON_NO_DISPOSITION = "no_disposition"
REASON_LEAVE_REJECTED = "leave_rejected"
REASON_LEAVE_CANCELLED = "leave_cancelled"

_OPEN_LOG = (LogApprovalStatus.PENDING, LogApprovalStatus.APPROVED)
_OPEN_ABSENCE = (SessionAbsenceStatus.PENDING_APPROVAL, SessionAbsenceStatus.APPROVED)
_OPEN_LEAVE = (LeaveStatus.PENDING, LeaveStatus.APPROVED)
_TERMINAL_LEAVE = (LeaveStatus.REJECTED, LeaveStatus.CANCELLED)
_CANDIDATE_SESSION = (SessionStatus.SCHEDULED, SessionStatus.CANCELLED)


def _leave_covers_date(leave: TherapistLeave, day: date) -> bool:
    return leave.start_date <= day <= leave.end_date


def _leave_applies_to_case(leave: TherapistLeave, case_id: int) -> bool:
    from app.services import leave_service

    scope = leave_service._leave_scope_ids(leave)
    if scope is None:
        return True
    return int(case_id) in scope


def list_unresolved_attendance_days(
    db: Session,
    *,
    therapist_user_id: int,
    from_date: date | None = None,
    to_date: date | None = None,
    lookback_days: int = 60,
) -> list[dict[str, Any]]:
    """Return structured unresolved attendance rows for a therapist."""
    today = today_ist()
    end = to_date or today
    start = from_date or (end - timedelta(days=max(lookback_days, 1)))
    if end < start:
        return []

    sessions = db.scalars(
        select(TherapySession)
        .where(
            TherapySession.therapist_user_id == therapist_user_id,
            TherapySession.scheduled_date >= start,
            TherapySession.scheduled_date <= end,
            TherapySession.status.in_(_CANDIDATE_SESSION),
        )
        .options(selectinload(TherapySession.case).selectinload(Case.child))
        .order_by(TherapySession.scheduled_date, TherapySession.id)
    ).all()
    if not sessions:
        return []

    session_ids = [s.id for s in sessions]
    case_ids = {s.case_id for s in sessions}

    logs = db.scalars(
        select(DailyLog).where(
            DailyLog.session_id.in_(session_ids),
            DailyLog.approval_status.in_(_OPEN_LOG),
        )
    ).all()
    logged_session_ids = {l.session_id for l in logs if l.session_id}

    absences = db.scalars(
        select(SessionAbsenceRequest).where(
            SessionAbsenceRequest.session_id.in_(session_ids),
            SessionAbsenceRequest.absence_type == SessionAbsenceType.CLIENT_ABSENT,
            SessionAbsenceRequest.status.in_(_OPEN_ABSENCE),
        )
    ).all()
    absence_session_ids = {a.session_id for a in absences}

    leaves = db.scalars(
        select(TherapistLeave).where(
            TherapistLeave.therapist_user_id == therapist_user_id,
            TherapistLeave.start_date <= end,
            TherapistLeave.end_date >= start,
        )
    ).all()

    out: list[dict[str, Any]] = []
    seen: set[tuple[int, str, int | None]] = set()
    for session in sessions:
        if session.scheduled_date > today:
            continue
        if session.id in logged_session_ids:
            continue
        if session.id in absence_session_ids:
            continue

        open_leave = next(
            (
                lv
                for lv in leaves
                if lv.status in _OPEN_LEAVE
                and _leave_covers_date(lv, session.scheduled_date)
                and _leave_applies_to_case(lv, session.case_id)
            ),
            None,
        )
        if open_leave:
            continue

        terminal_leave = next(
            (
                lv
                for lv in leaves
                if lv.status in _TERMINAL_LEAVE
                and _leave_covers_date(lv, session.scheduled_date)
                and _leave_applies_to_case(lv, session.case_id)
            ),
            None,
        )
        if session.status == SessionStatus.CANCELLED:
            reason = REASON_SESSION_CANCELLED
        elif terminal_leave and terminal_leave.status == LeaveStatus.REJECTED:
            reason = REASON_LEAVE_REJECTED
        elif terminal_leave and terminal_leave.status == LeaveStatus.CANCELLED:
            reason = REASON_LEAVE_CANCELLED
        else:
            reason = REASON_NO_DISPOSITION

        key = (session.case_id, session.scheduled_date.isoformat(), session.id)
        if key in seen:
            continue
        seen.add(key)

        case = session.case
        out.append(
            {
                "case_id": session.case_id,
                "case_code": case.case_code if case else None,
                "child_name": case.child.full_name if case and case.child else None,
                "date": session.scheduled_date.isoformat(),
                "session_id": session.id,
                "session_status": session.status.value
                if hasattr(session.status, "value")
                else str(session.status),
                "reason": reason,
                "leave_id": terminal_leave.id if terminal_leave else None,
            }
        )
    return out


_GATE_REASONS = frozenset(
    {REASON_LEAVE_REJECTED, REASON_LEAVE_CANCELLED, REASON_SESSION_CANCELLED}
)


def unresolved_for_gates(
    db: Session, *, therapist_user_id: int, **kwargs: Any
) -> list[dict[str, Any]]:
    """Subset that blocks new leave / invoice submit (not every open Needs-log day)."""
    return [
        r
        for r in list_unresolved_attendance_days(db, therapist_user_id=therapist_user_id, **kwargs)
        if r.get("reason") in _GATE_REASONS
    ]


def unresolved_count(db: Session, *, therapist_user_id: int, **kwargs: Any) -> int:
    return len(list_unresolved_attendance_days(db, therapist_user_id=therapist_user_id, **kwargs))


def assert_no_unresolved_for_new_leave(db: Session, *, therapist_user_id: int) -> None:
    rows = unresolved_for_gates(db, therapist_user_id=therapist_user_id)
    if not rows:
        return
    sample = ", ".join(
        f"{r.get('case_code') or r['case_id']} on {r['date']}" for r in rows[:3]
    )
    more = f" (+{len(rows) - 3} more)" if len(rows) > 3 else ""
    raise ValueError(
        "Looks like we still need a disposition for "
        f"{len(rows)} earlier day(s) before a new leave request "
        f"({sample}{more}). "
        "Please submit a session log, file a child absence, or re-request leave for those days."
    )


def assert_no_unresolved_for_invoice_month(
    db: Session,
    *,
    therapist_user_id: int,
    year: int,
    month: int,
) -> None:
    from calendar import monthrange

    start = date(year, month, 1)
    end = date(year, month, monthrange(year, month)[1])
    # Only gate past/today within the invoice month (future days in month are fine).
    today = today_ist()
    end = min(end, today)
    if end < start:
        return
    rows = unresolved_for_gates(
        db, therapist_user_id=therapist_user_id, from_date=start, to_date=end
    )
    if not rows:
        return
    raise ValueError(
        "Looks like we still need a few attendance details before we can submit this month's invoice. "
        f"{len(rows)} day(s) still need a session log, child absence, or leave. "
        "Would you like to continue from where you left off on Invoices?"
    )


def build_unresolved_invoice_line(row: dict[str, Any]) -> dict[str, Any]:
    """Therapist invoice line for an unexplained cancelled / undisposed session."""
    reason = row.get("reason") or REASON_NO_DISPOSITION
    if reason == REASON_SESSION_CANCELLED:
        hint = "Session was cancelled with no log or absence — add a log if the visit happened, or file child absence / leave."
    elif reason == REASON_LEAVE_REJECTED:
        hint = "Leave was not approved for this day — add a session log, child absence, or a new leave request."
    elif reason == REASON_LEAVE_CANCELLED:
        hint = "Leave was cancelled for this day — add a session log, child absence, or a new leave request."
    else:
        hint = "This day still needs a session log, child absence, or leave before payout is clear."

    return {
        "session_id": row.get("session_id"),
        "session_date": row.get("date"),
        "line_type": "INCLUDED",
        "ui_label": "Needs log or absence",
        "amount_inr": 0.0,
        "display_amount_inr": 0.0,
        "included": False,
        "affects_net": False,
        "breakdown_bucket": labels.BUCKET_PENDING,
        "status_tag": labels.PENDING_TAG,
        "pending_reason": hint,
        "line_kind": "SESSION_CANCELLED_UNEXPLAINED"
        if reason == REASON_SESSION_CANCELLED
        else "ATTENDANCE_NEEDS_DISPOSITION",
        "flags": {
            "needs_disposition": True,
            "disposition_reason": reason,
            "pending_reason": hint,
        },
    }


def group_unresolved_by_case(rows: list[dict[str, Any]]) -> dict[int, list[dict[str, Any]]]:
    by_case: dict[int, list[dict[str, Any]]] = {}
    for row in rows:
        by_case.setdefault(int(row["case_id"]), []).append(row)
    return by_case
