"""HR Session discrepancies report — multi-sheet data builders."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.timezone import ensure_utc_aware, today_ist
from app.models.audit_event import AuditEvent
from app.models.case import Case, CaseStatus
from app.models.daily_log import DailyLog
from app.models.session import Session as TherapySession
from app.models.session import SessionStatus
from app.models.user import User
from app.services.reports_export_helpers import (
    MAX_EXPORT_ROWS,
    active_therapists_by_case,
    case_manager,
    case_owner_export_fields,
    enum_value,
    mentor_for_therapist,
    parse_iso_date,
    scoped_cases,
    user_display_name,
)
from app.services.session_discrepancy_rules import (
    effective_duration_minutes,
    evaluate_session_anomalies,
    fmt_time_ist,
    fmt_time_only,
)

_FORGOT_AUDIT_ACTIONS = frozenset({"complete_forgotten", "create_manual", "create_manual_walk_in"})


def _case_allowed(db: Session, user: User | None, case: Case | None) -> bool:
    from app.core.permissions import case_scope_check

    if not case or not user:
        return True
    return case_scope_check(db, user, case)


def _load_sessions_in_range(
    db: Session,
    case_ids: list[int],
    d_from: date,
    d_to: date,
    *,
    therapist_user_id: int | None = None,
    case_id: int | None = None,
) -> list[TherapySession]:
    if not case_ids:
        return []
    stmt = (
        select(TherapySession)
        .where(
            TherapySession.case_id.in_(case_ids),
            TherapySession.scheduled_date >= d_from,
            TherapySession.scheduled_date <= d_to,
        )
        .options(
            selectinload(TherapySession.daily_log),
            selectinload(TherapySession.case),
        )
        .order_by(TherapySession.scheduled_date, TherapySession.start_time, TherapySession.id)
    )
    if therapist_user_id:
        stmt = stmt.where(TherapySession.therapist_user_id == therapist_user_id)
    if case_id:
        stmt = stmt.where(TherapySession.case_id == case_id)
    return list(db.scalars(stmt.limit(MAX_EXPORT_ROWS)).all())


def _audit_action_by_session(db: Session, session_ids: list[int]) -> dict[int, str]:
    if not session_ids:
        return {}
    rows = db.execute(
        select(AuditEvent.entity_id, AuditEvent.action, AuditEvent.created_at)
        .where(
            AuditEvent.entity_type == "session",
            AuditEvent.action.in_(tuple(_FORGOT_AUDIT_ACTIONS)),
            AuditEvent.entity_id.in_([str(sid) for sid in session_ids]),
        )
        .order_by(AuditEvent.created_at.asc())
    ).all()
    out: dict[int, str] = {}
    for entity_id, action, _created in rows:
        try:
            sid = int(entity_id)
        except (TypeError, ValueError):
            continue
        if sid not in out:
            out[sid] = action
    return out


def _completed_same_day_counts(sessions: list[TherapySession]) -> dict[tuple[int, int, date], int]:
    counts: dict[tuple[int, int, date], int] = defaultdict(int)
    for s in sessions:
        if s.status != SessionStatus.COMPLETED or s.case_id is None:
            continue
        key = (s.case_id, s.therapist_user_id, s.scheduled_date)
        counts[key] += 1
    return dict(counts)


def _next_started_before_prior_log_flags(sessions: list[TherapySession]) -> dict[int, bool]:
    """Flag session N if session N+1 started before N's log was submitted."""
    by_pair: dict[tuple[int, int], list[TherapySession]] = defaultdict(list)
    for s in sessions:
        if s.case_id is None:
            continue
        by_pair[(s.case_id, s.therapist_user_id)].append(s)

    flagged: dict[int, bool] = {}
    for group in by_pair.values():
        ordered = sorted(
            group,
            key=lambda x: (x.scheduled_date, x.actual_start_at or datetime.min, x.id),
        )
        for idx, sess in enumerate(ordered):
            if idx + 1 >= len(ordered):
                break
            nxt = ordered[idx + 1]
            log = sess.daily_log
            if log is None or log.submitted_at is None:
                continue
            nxt_start = nxt.actual_start_at
            if nxt_start is None:
                continue
            submitted = ensure_utc_aware(log.submitted_at)
            started = ensure_utc_aware(nxt_start)
            if submitted and started and started < submitted:
                flagged[nxt.id] = True
    return flagged


def therapists_missing_logs_rows(
    db: Session,
    *,
    d_from: date,
    d_to: date,
    user: User | None = None,
    product_module: str | None = None,
    case_manager_user_id: int | list[int] | None = None,
    case_statuses: list[str] | None = None,
    therapist_user_id: int | None = None,
    case_id: int | None = None,
) -> list[dict[str, Any]]:
    cases = scoped_cases(
        db,
        user,
        product_module=product_module,
        case_manager_user_id=case_manager_user_id,
        case_statuses=case_statuses,
    )
    case_ids = [c.id for c in cases if _case_allowed(db, user, c)]
    if case_id is not None:
        case_ids = [cid for cid in case_ids if cid == case_id]
    sessions = _load_sessions_in_range(
        db, case_ids, d_from, d_to, therapist_user_id=therapist_user_id, case_id=case_id
    )
    missing_by_pair: dict[tuple[int, int], list[date]] = defaultdict(list)
    cases_by_id = {c.id: c for c in cases}
    for s in sessions:
        if s.status != SessionStatus.COMPLETED or s.daily_log is not None:
            continue
        if s.case_id is None:
            continue
        missing_by_pair[(s.therapist_user_id, s.case_id)].append(s.scheduled_date)

    rows: list[dict[str, Any]] = []
    for (therapist_id, cid), dates in missing_by_pair.items():
        case = cases_by_id.get(cid)
        if not case:
            continue
        therapist = db.get(User, therapist_id)
        cm = case_manager(db, case)
        mentor = mentor_for_therapist(db, therapist_id)
        rows.append(
            {
                **case_owner_export_fields(case, therapist=therapist, case_manager=cm),
                "Mentor": user_display_name(mentor),
                "Missing Logs In Period": len(dates),
                "Oldest Missing Session Date": min(dates).isoformat(),
                "Newest Missing Session Date": max(dates).isoformat(),
                "Case Status": enum_value(case.status),
                "Product Module": case.product_module or "",
            }
        )
    rows.sort(key=lambda r: (-int(r["Missing Logs In Period"]), r["Case ID"]))
    return rows[:MAX_EXPORT_ROWS]


def session_anomalies_rows(
    db: Session,
    *,
    d_from: date,
    d_to: date,
    user: User | None = None,
    product_module: str | None = None,
    case_manager_user_id: int | list[int] | None = None,
    case_statuses: list[str] | None = None,
    therapist_user_id: int | None = None,
    case_id: int | None = None,
) -> list[dict[str, Any]]:
    cases = scoped_cases(
        db,
        user,
        product_module=product_module,
        case_manager_user_id=case_manager_user_id,
        case_statuses=case_statuses,
    )
    case_ids = [c.id for c in cases if _case_allowed(db, user, c)]
    if case_id is not None:
        case_ids = [cid for cid in case_ids if cid == case_id]
    sessions = _load_sessions_in_range(
        db, case_ids, d_from, d_to, therapist_user_id=therapist_user_id, case_id=case_id
    )
    audit_map = _audit_action_by_session(db, [s.id for s in sessions])
    same_day = _completed_same_day_counts(sessions)
    prior_log_flags = _next_started_before_prior_log_flags(sessions)

    rows: list[dict[str, Any]] = []
    for s in sessions:
        case = s.case
        if not case or not _case_allowed(db, user, case):
            continue
        log = s.daily_log
        therapist = db.get(User, s.therapist_user_id)
        cm = case_manager(db, case)
        day_key = (s.case_id, s.therapist_user_id, s.scheduled_date)
        result = evaluate_session_anomalies(
            s,
            log,
            case,
            audit_action=audit_map.get(s.id),
            completed_same_day_count=same_day.get(day_key, 0),
            next_session_started_before_prior_log=prior_log_flags.get(s.id, False),
        )
        if not result.codes:
            continue

        duration = effective_duration_minutes(s, log)
        log_submitted = "Yes" if log and log.submitted_at else "No"
        approval = ""
        if log is not None:
            approval = enum_value(log.approval_status)

        rows.append(
            {
                **case_owner_export_fields(case, therapist=therapist, case_manager=cm),
                "Case Status": enum_value(case.status),
                "Product Module": case.product_module or "",
                "Service Type": case.service_type or "",
                "Session ID": s.id,
                "Session Date": s.scheduled_date.isoformat(),
                "Scheduled Start": fmt_time_only(s.start_time),
                "Scheduled End": fmt_time_only(s.end_time),
                "Actual Start": fmt_time_ist(s.actual_start_at),
                "Actual End": fmt_time_ist(s.actual_end_at),
                "Session Duration (min)": duration if duration is not None else "",
                "Session Status": enum_value(s.status),
                "Session Log Submitted": log_submitted,
                "Log Approval Status": approval,
                "Late Addition": "Yes" if log and log.late_addition else "No",
                "Auto Ended": "Yes" if s.auto_ended else "No",
                "Anomaly Codes": "|".join(result.codes),
                "Guidance": result.guidance,
            }
        )
    rows.sort(key=lambda r: (r["Session Date"], r.get("Session ID", 0)), reverse=True)
    return rows[:MAX_EXPORT_ROWS]


def active_cases_no_log_in_period_rows(
    db: Session,
    *,
    d_from: date,
    d_to: date,
    user: User | None = None,
    product_module: str | None = None,
    case_manager_user_id: int | list[int] | None = None,
    case_statuses: list[str] | None = None,
    therapist_user_id: int | None = None,
    case_id: int | None = None,
) -> list[dict[str, Any]]:
    silent_statuses = case_statuses or [CaseStatus.ACTIVE.value]
    cases = scoped_cases(
        db,
        user,
        product_module=product_module,
        case_manager_user_id=case_manager_user_id,
        case_statuses=silent_statuses,
    )
    case_ids = [c.id for c in cases if _case_allowed(db, user, c)]
    if case_id is not None:
        case_ids = [cid for cid in case_ids if cid == case_id]

    if not case_ids:
        return []

    logged_case_ids = {
        int(cid)
        for cid, in db.execute(
            select(TherapySession.case_id)
            .join(DailyLog, DailyLog.session_id == TherapySession.id)
            .where(
                TherapySession.case_id.in_(case_ids),
                TherapySession.scheduled_date >= d_from,
                TherapySession.scheduled_date <= d_to,
            )
            .distinct()
        ).all()
    }

    sessions = _load_sessions_in_range(db, case_ids, d_from, d_to, therapist_user_id=therapist_user_id)
    missing_completed_by_case: dict[int, int] = defaultdict(int)
    for s in sessions:
        if s.status == SessionStatus.COMPLETED and s.daily_log is None and s.case_id:
            missing_completed_by_case[s.case_id] += 1

    therapists = active_therapists_by_case(db, case_ids)
    rows: list[dict[str, Any]] = []
    for case in cases:
        if case.id not in case_ids:
            continue
        if case.id in logged_case_ids:
            continue
        therapist = therapists.get(case.id)
        if therapist_user_id and (not therapist or therapist.id != therapist_user_id):
            continue
        cm = case_manager(db, case)
        rows.append(
            {
                **case_owner_export_fields(case, therapist=therapist, case_manager=cm),
                "Case Status": enum_value(case.status),
                "Product Module": case.product_module or "",
                "Completed Without Log In Period": missing_completed_by_case.get(case.id, 0),
            }
        )
    rows.sort(key=lambda r: r["Case ID"])
    return rows[:MAX_EXPORT_ROWS]


def forgot_to_log_audit_rows(
    db: Session,
    *,
    d_from: date,
    d_to: date,
    user: User | None = None,
    product_module: str | None = None,
    case_manager_user_id: int | list[int] | None = None,
    case_statuses: list[str] | None = None,
    therapist_user_id: int | None = None,
    case_id: int | None = None,
) -> list[dict[str, Any]]:
    cases = scoped_cases(
        db,
        user,
        product_module=product_module,
        case_manager_user_id=case_manager_user_id,
        case_statuses=case_statuses,
    )
    cases_by_id = {c.id: c for c in cases if _case_allowed(db, user, c)}
    case_ids = list(cases_by_id.keys())
    if case_id is not None:
        case_ids = [cid for cid in case_ids if cid == case_id]
    if not case_ids:
        return []

    audit_rows = db.scalars(
        select(AuditEvent)
        .where(
            AuditEvent.entity_type == "session",
            AuditEvent.action.in_(tuple(_FORGOT_AUDIT_ACTIONS)),
        )
        .order_by(AuditEvent.created_at.desc())
        .limit(MAX_EXPORT_ROWS * 2)
    ).all()

    session_ids: list[int] = []
    for ev in audit_rows:
        try:
            session_ids.append(int(ev.entity_id))
        except (TypeError, ValueError):
            continue

    if not session_ids:
        return []

    sessions = {
        s.id: s
        for s in db.scalars(
            select(TherapySession)
            .where(
                TherapySession.id.in_(session_ids),
                TherapySession.case_id.in_(case_ids),
                TherapySession.scheduled_date >= d_from,
                TherapySession.scheduled_date <= d_to,
            )
            .options(selectinload(TherapySession.daily_log), selectinload(TherapySession.case))
        ).all()
    }

    rows: list[dict[str, Any]] = []
    for ev in audit_rows:
        try:
            sid = int(ev.entity_id)
        except (TypeError, ValueError):
            continue
        session = sessions.get(sid)
        if not session or not session.case:
            continue
        if therapist_user_id and session.therapist_user_id != therapist_user_id:
            continue
        case = session.case
        therapist = db.get(User, session.therapist_user_id)
        log = session.daily_log
        duration = effective_duration_minutes(session, log)
        rows.append(
            {
                "Audit Time": ev.created_at.isoformat() if ev.created_at else "",
                "Audit Action": ev.action,
                "Session ID": session.id,
                **case_owner_export_fields(case, therapist=therapist, case_manager=case_manager(db, case)),
                "Session Date": session.scheduled_date.isoformat(),
                "Duration (min)": duration if duration is not None else "",
                "Log Submitted": "Yes" if log and log.submitted_at else "No",
                "Log Approval Status": enum_value(log.approval_status) if log else "",
            }
        )
    return rows[:MAX_EXPORT_ROWS]


def build_session_discrepancies_report(
    db: Session,
    *,
    date_from: str | None = None,
    date_to: str | None = None,
    user: User | None = None,
    product_module: str | None = None,
    case_manager_user_id: int | list[int] | None = None,
    case_statuses: list[str] | None = None,
    therapist_user_id: int | None = None,
    case_id: int | None = None,
) -> dict[str, Any]:
    today = today_ist()
    d_from = parse_iso_date(date_from, today.replace(day=1))
    d_to = parse_iso_date(date_to, today)
    if d_from > d_to:
        d_from, d_to = d_to, d_from

    common = dict(
        d_from=d_from,
        d_to=d_to,
        user=user,
        product_module=product_module,
        case_manager_user_id=case_manager_user_id,
        case_statuses=case_statuses,
        therapist_user_id=therapist_user_id,
        case_id=case_id,
    )

    sheet_a = therapists_missing_logs_rows(db, **common)
    sheet_b = session_anomalies_rows(db, **common)
    sheet_c = active_cases_no_log_in_period_rows(db, **common)
    sheet_d = forgot_to_log_audit_rows(db, **common)

    return {
        "rows": sheet_b,
        "sheets": {
            "Therapists missing logs": sheet_a,
            "Session anomalies": sheet_b,
            "Active cases no log in period": sheet_c,
            "Forgot-to-log and manual": sheet_d,
        },
        "count": len(sheet_a) + len(sheet_b) + len(sheet_c) + len(sheet_d),
        "period": {"date_from": d_from.isoformat(), "date_to": d_to.isoformat()},
    }
