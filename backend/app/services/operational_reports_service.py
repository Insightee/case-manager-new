"""Operational report queries for HR / admin exports."""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any, Optional

from app.core.timezone import today_ist

from sqlalchemy import extract, func, select
from sqlalchemy.orm import Session, selectinload

from app.core.incident_catalog import category_label, subcategory_label
from app.core.permissions import RoleName, case_scope_check, user_has_permission
from app.core.support_status import canonical_incident_status, canonical_label, canonical_ticket_status
from app.models.assignment import CaseAssignment, CaseAssignmentStatus
from app.models.case import Case, CaseStatus
from app.models.case_manager_meeting import CaseManagerMeeting, MeetingStatus, MeetingType
from app.models.daily_log import DailyLog, LogApprovalStatus
from app.models.incident import Incident, normalize_incident_status
from app.models.ledger_billing import BillableStatus, BillingLedger
from app.models.session import Session as TherapySession
from app.models.session import SessionStatus
from app.models.session_absence import SessionAbsenceRequest, SessionAbsenceStatus, SessionAbsenceType
from app.models.audit_event import AuditEvent
from app.models.support_ticket import SupportTicket
from app.models.user import User
from app.services import case_service, leave_policy_service
from app.services.support_access_service import can_read_incident
from app.services.reports_export_helpers import (
    INACTIVE_DAYS_THRESHOLD,
    MAX_EXPORT_ROWS,
    active_assignment,
    active_therapists_by_case,
    apply_case_manager_filter,
    assignment_segments_for_month,
    assignment_therapist,
    billing_snapshot_report_columns,
    calendar_days_in_month,
    case_manager,
    case_people_export_fields,
    cases_by_ids,
    days_since,
    enum_value,
    export_therapist_id,
    last_completed_session_date,
    leave_days_in_month,
    mentor_for_therapist,
    month_bounds,
    month_long_label,
    is_homecare_case,
    is_shadow_case,
    monthly_report_submitted,
    normalize_month,
    parent_by_child,
    parse_iso_date,
    scoped_cases,
    THERAPIST_LOG_COMPLIANCE_MIN_AGE_DAYS,
    user_display_name,
)

_TERMINAL_CASE_STATUSES = frozenset(
    {CaseStatus.CLOSED.value, CaseStatus.DEACTIVATED.value}
)


def _therapist_status_label(therapist: User | None) -> str:
    """Prefer employment_status when present; else User.is_active → Active/Inactive."""
    if not therapist:
        return ""
    emp = getattr(therapist, "employment_status", None)
    if emp is not None:
        return enum_value(emp) or ("Active" if therapist.is_active else "Inactive")
    return "Active" if therapist.is_active else "Inactive"


def _case_allowed(db: Session, user: User | None, case: Case | None) -> bool:
    if not case or not user:
        return True
    return case_scope_check(db, user, case)


def _user_has_role(db: Session, user_id: int, role_name: str) -> bool:
    user = db.get(User, user_id)
    if not user:
        return False
    return role_name in (user.role_names or [])


def _reporter_role_label(reporter: User | None) -> str:
    if not reporter:
        return ""
    roles = reporter.role_names or []
    for role in (
        RoleName.PARENT,
        RoleName.THERAPIST,
        RoleName.CASE_MANAGER,
        RoleName.HR,
        RoleName.ADMIN,
        RoleName.SUPERVISOR,
    ):
        if role.value in roles:
            return role.value.replace("_", " ").title()
    return roles[0].replace("_", " ").title() if roles else ""


def _resolution_time_label(created: datetime | None, resolved: datetime | None) -> str:
    if not created or not resolved:
        return ""
    delta = resolved - created
    days = delta.days
    if days == 0:
        hours = delta.seconds // 3600
        if hours == 0:
            return f"{delta.seconds // 60} min"
        return f"{hours} hr"
    return f"{days} day{'s' if days != 1 else ''}"


def run_report(
    db: Session,
    report_key: str,
    *,
    user: User | None = None,
    month: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    product_module: str | None = None,
    case_manager_user_id: int | list[int] | None = None,
    therapist_user_id: int | None = None,
    case_id: int | None = None,
    case_statuses: list[str] | None = None,
) -> dict[str, Any]:
    ym = normalize_month(month)
    if report_key == "session-discrepancies":
        from app.services.session_discrepancy_report_service import build_session_discrepancies_report

        return build_session_discrepancies_report(
            db,
            date_from=date_from,
            date_to=date_to,
            user=user,
            product_module=product_module,
            case_manager_user_id=case_manager_user_id,
            case_statuses=case_statuses,
            therapist_user_id=therapist_user_id,
            case_id=case_id,
        )
    if report_key == "bulk-attendance":
        rows = bulk_attendance_rows(
            db,
            ym,
            user=user,
            product_module=product_module,
            case_manager_user_id=case_manager_user_id,
        )
        return {"rows": rows, "count": len(rows)}
    if report_key == "session-log-detail":
        rows = session_log_detail_rows(
            db,
            date_from=date_from,
            date_to=date_to,
            user=user,
            product_module=product_module,
            case_manager_user_id=case_manager_user_id,
            therapist_user_id=therapist_user_id,
            case_id=case_id,
        )
        return {"rows": rows, "count": len(rows)}
    if report_key == "session-monthly-summary":
        client_rows, therapist_rows = session_monthly_summary_rows(
            db,
            ym,
            user=user,
            product_module=product_module,
            case_manager_user_id=case_manager_user_id,
        )
        return {
            "rows": client_rows,
            "sheets": {
                "Client summary": client_rows,
                "Therapist summary": therapist_rows,
            },
            "count": len(client_rows) + len(therapist_rows),
        }
    if report_key == "replacement-history":
        rows = replacement_history_rows(db, ym, user=user, product_module=product_module)
        return {"rows": rows, "count": len(rows)}
    if report_key == "support-tickets-parent":
        rows = support_tickets_parent_rows(db, ym, user=user, product_module=product_module)
        return {"rows": rows, "count": len(rows)}
    if report_key == "incident-reports":
        rows = incident_reports_rows(
            db,
            ym,
            user=user,
            product_module=product_module,
            case_manager_user_id=case_manager_user_id,
        )
        return {"rows": rows, "count": len(rows)}
    if report_key == "cm-meetings":
        detail_rows, summary_rows = cm_meetings_rows(
            db,
            ym,
            user=user,
            product_module=product_module,
            case_manager_user_id=case_manager_user_id,
        )
        return {
            "rows": detail_rows,
            "sheets": {
                "Meeting details": detail_rows,
                "Monthly summary": summary_rows,
            },
            "summaryRows": summary_rows,
            "count": len(detail_rows),
        }
    if report_key == "inactive-clients":
        rows = inactive_clients_rows(
            db,
            user=user,
            product_module=product_module,
            case_manager_user_id=case_manager_user_id,
        )
        return {"rows": rows, "count": len(rows)}
    if report_key == "parent-portal-usage":
        rows = parent_portal_usage_rows(
            db,
            user=user,
            product_module=product_module,
            case_manager_user_id=case_manager_user_id,
        )
        return {"rows": rows, "count": len(rows)}
    if report_key == "therapist-log-compliance":
        rows = therapist_log_compliance_rows(
            db,
            user=user,
            product_module=product_module,
            case_manager_user_id=case_manager_user_id,
        )
        return {"rows": rows, "count": len(rows)}
    raise ValueError(f"Unknown operational report: {report_key}")


def bulk_attendance_rows(
    db: Session,
    ym: str,
    *,
    user: User | None = None,
    product_module: str | None = None,
    case_manager_user_id: int | list[int] | None = None,
) -> list[dict[str, Any]]:
    start, end = month_bounds(ym)
    year = int(ym.split("-")[0])
    cal_days = calendar_days_in_month(ym)
    month_label = month_long_label(ym)

    cases = scoped_cases(
        db,
        user,
        product_module=product_module,
        case_manager_user_id=case_manager_user_id,
        active_only=True,
    )
    case_ids = [c.id for c in cases]
    if not case_ids:
        return []

    segments_by_case = assignment_segments_for_month(db, case_ids, start, end)
    month_sessions = _load_sessions_in_range(db, case_ids, start, end)
    absence_by_session = _absence_by_session(db, [s.id for s in month_sessions])
    parents = parent_by_child(db, {c.child_id for c in cases if c.child_id})
    therapist_ids = {
        seg["therapist_user_id"]
        for segs in segments_by_case.values()
        for seg in segs
    }
    # Fallback single-active path may still need therapists not in segments.
    for case in cases:
        if case.id not in segments_by_case:
            assign = active_assignment(db, case.id)
            if assign:
                therapist_ids.add(assign.therapist_user_id)
    therapists = {
        u.id: u
        for u in db.scalars(select(User).where(User.id.in_(therapist_ids or {-1}))).all()
    }

    rows: list[dict[str, Any]] = []
    for case in cases:
        if not _case_allowed(db, user, case):
            continue
        if len(rows) >= MAX_EXPORT_ROWS:
            break
        parent_info = parents.get(case.child_id or -1, {})
        cm = case_manager(db, case)
        segments = segments_by_case.get(case.id) or []
        if not segments:
            assign = active_assignment(db, case.id)
            therapist = assignment_therapist(db, assign)
            if not therapist:
                continue
            segments = [
                {
                    "assignment": assign,
                    "therapist_user_id": therapist.id,
                    "start": start,
                    "end": end,
                }
            ]

        for seg in segments:
            if len(rows) >= MAX_EXPORT_ROWS:
                break
            therapist = therapists.get(seg["therapist_user_id"])
            if not therapist:
                continue
            seg_sessions = _sessions_for_segment(
                month_sessions, case.id, seg["start"], seg["end"]
            )
            stats = _stats_from_sessions(seg_sessions)
            metrics = _billable_metrics_from_sessions(
                case, seg_sessions, absence_by_session
            )
            pending, rejected = _log_gaps_from_sessions(seg_sessions)
            leave = leave_days_in_month(db, therapist.id, ym)
            balance = leave_policy_service.get_leave_balance(
                db, therapist, year=year, as_of=end
            )
            hours = _hours_from_sessions(seg_sessions)

            rows.append(
                {
                    "Month": month_label,
                    **case_people_export_fields(
                        case, therapist=therapist, parent_info=parent_info
                    ),
                    "Assignment Start": seg["start"].isoformat(),
                    "Assignment End": seg["end"].isoformat(),
                    "Service Type": case.service_type or case.product_module or "",
                    "Case Manager": user_display_name(cm),
                    "Total Calendar Days": cal_days,
                    "Segment Calendar Days": (seg["end"] - seg["start"]).days + 1,
                    "Scheduled Sessions": stats.get("scheduled", 0),
                    "Sessions Completed": stats.get("completed", 0),
                    "Approved Sessions": metrics.get("approved_sessions", 0),
                    "Approved Child Absence (Billable)": metrics.get(
                        "approved_child_absence", 0
                    ),
                    "Child Absence (All)": stats.get("client_absent", 0),
                    "Therapist Leave": stats.get("therapist_leave", 0),
                    "Completed Missing Logs": _missing_logs_from_sessions(seg_sessions),
                    "Logs Pending Approval": pending,
                    "Logs Rejected": rejected,
                    "Leave Paid Days": leave["paid"],
                    "Leave Unpaid Days": leave["unpaid"],
                    "Leave Credits Remaining": balance.get(
                        "leave_credit_pending", balance.get("paid_remaining", 0)
                    ),
                    "Total Session Hours": round(hours, 2),
                    "Billable Sessions": metrics.get("billable_sessions", 0),
                    "Monthly Report Submitted": (
                        "Yes" if monthly_report_submitted(db, case.id, ym) else "No"
                    ),
                }
            )
    return rows


def session_log_detail_rows(
    db: Session,
    *,
    date_from: str | None = None,
    date_to: str | None = None,
    user: User | None = None,
    product_module: str | None = None,
    case_manager_user_id: int | list[int] | None = None,
    therapist_user_id: int | None = None,
    case_id: int | None = None,
) -> list[dict[str, Any]]:
    today = today_ist()
    d_from = parse_iso_date(date_from, today.replace(day=1))
    d_to = parse_iso_date(date_to, today)

    stmt = (
        select(TherapySession)
        .join(Case, TherapySession.case_id == Case.id)
        .options(
            selectinload(TherapySession.case).selectinload(Case.child),
            selectinload(TherapySession.daily_log),
        )
        .where(TherapySession.scheduled_date >= d_from, TherapySession.scheduled_date <= d_to)
        .order_by(TherapySession.scheduled_date.desc(), TherapySession.id.desc())
    )
    if product_module:
        stmt = stmt.where(Case.product_module == product_module)
    stmt = apply_case_manager_filter(stmt, Case.case_manager_user_id, case_manager_user_id)
    if therapist_user_id:
        stmt = stmt.where(TherapySession.therapist_user_id == therapist_user_id)
    if case_id:
        stmt = stmt.where(TherapySession.case_id == case_id)

    sessions = db.scalars(stmt.limit(MAX_EXPORT_ROWS)).all()
    absence_by_session = _absence_by_session(db, [s.id for s in sessions])
    billable_by_session = _billable_by_session(db, [s.id for s in sessions])
    parents = parent_by_child(
        db, {s.case.child_id for s in sessions if s.case and s.case.child_id}
    )

    rows: list[dict[str, Any]] = []
    for s in sessions:
        case = s.case
        if not _case_allowed(db, user, case):
            continue
        therapist = db.get(User, s.therapist_user_id)
        cm = case_manager(db, case) if case else None
        mentor = mentor_for_therapist(db, s.therapist_user_id)
        log = s.daily_log
        absence = absence_by_session.get(s.id)
        parent_info = parents.get(case.child_id, {}) if case and case.child_id else {}

        duration_mins: int | str = ""
        if s.actual_start_at and s.actual_end_at:
            duration_mins = int((s.actual_end_at - s.actual_start_at).total_seconds() / 60)
        elif s.start_time and s.end_time:
            start_dt = datetime.combine(s.scheduled_date, s.start_time)
            end_dt = datetime.combine(s.scheduled_date, s.end_time)
            duration_mins = int((end_dt - start_dt).total_seconds() / 60)

        pending_log = s.status == SessionStatus.COMPLETED and log is None
        days_pending: int | str = ""
        if pending_log:
            days_pending = days_since(s.scheduled_date, as_of=today) or ""

        billable_label = _session_billable_label(case, s, log, absence, billable_by_session.get(s.id, ""))

        rows.append(
            {
                **case_people_export_fields(case, therapist=therapist, parent_info=parent_info),
                "Mentor": user_display_name(mentor),
                "Case Manager": user_display_name(cm),
                "Service Type": (case.service_type if case else "") or (case.product_module if case else ""),
                "Session Date": s.scheduled_date.isoformat(),
                "Scheduled Start": s.start_time.isoformat() if s.start_time else "",
                "Scheduled End": s.end_time.isoformat() if s.end_time else "",
                "Actual Start": s.actual_start_at.isoformat() if s.actual_start_at else "",
                "Actual End": s.actual_end_at.isoformat() if s.actual_end_at else "",
                "Session Duration (min)": duration_mins,
                "Session Status": enum_value(s.status),
                "Cancellation Reason": s.cancellation_reason or "",
                "Session Log Submitted": "Yes" if log and log.submitted_at else "No",
                "Submission Date": log.submitted_at.isoformat() if log and log.submitted_at else "",
                "Session Notes Submitted": "Yes" if log and (log.session_notes or log.activities_done) else "No",
                "Log Approval Status": log.approval_status if log else "",
                "Child Absence Approval": absence.get("status", "") if absence else "",
                "Pending Session Log": "Yes" if pending_log else "No",
                "Days Pending": days_pending,
                "Billable": billable_label,
                "Remarks": log.review_note if log and log.review_note else "",
            }
        )
    return rows


def session_monthly_summary_rows(
    db: Session,
    ym: str,
    *,
    user: User | None = None,
    product_module: str | None = None,
    case_manager_user_id: int | list[int] | None = None,
) -> tuple[list[dict], list[dict]]:
    cases = scoped_cases(
        db,
        user,
        product_module=product_module,
        case_manager_user_id=case_manager_user_id,
    )
    case_ids = [c.id for c in cases if _case_allowed(db, user, c)]
    start, end = month_bounds(ym)
    segments_by_case = assignment_segments_for_month(db, case_ids, start, end)
    month_sessions = _load_sessions_in_range(db, case_ids, start, end)
    absence_by_session = _absence_by_session(db, [s.id for s in month_sessions])
    parents = parent_by_child(db, {c.child_id for c in cases if c.child_id and c.id in case_ids})

    therapist_ids: set[int] = {
        seg["therapist_user_id"]
        for segs in segments_by_case.values()
        for seg in segs
    }
    for case in cases:
        if case.id in case_ids and case.id not in segments_by_case:
            assign = active_assignment(db, case.id)
            if assign:
                therapist_ids.add(assign.therapist_user_id)
    therapists = {
        u.id: u
        for u in db.scalars(select(User).where(User.id.in_(therapist_ids or {-1}))).all()
    }

    client_rows: list[dict[str, Any]] = []
    therapist_agg: dict[int, dict[str, Any]] = defaultdict(
        lambda: {
            "scheduled": 0,
            "conducted": 0,
            "logs_submitted": 0,
            "pending_logs": 0,
            "child_absence": 0,
            "therapist_leave": 0,
            "cancelled": 0,
            "rescheduled": 0,
            "billable": 0,
            "hours": 0.0,
            "active_clients": set(),
        }
    )

    for case in cases:
        if case.id not in case_ids:
            continue
        if len(client_rows) >= MAX_EXPORT_ROWS:
            break
        parent_info = parents.get(case.child_id or -1, {})
        segments = segments_by_case.get(case.id) or []
        if not segments:
            assign = active_assignment(db, case.id)
            therapist = assignment_therapist(db, assign)
            if therapist:
                segments = [
                    {
                        "assignment": assign,
                        "therapist_user_id": therapist.id,
                        "start": start,
                        "end": end,
                    }
                ]
            else:
                # No therapist — still emit one case row with empty therapist fields.
                segments = [
                    {
                        "assignment": None,
                        "therapist_user_id": None,
                        "start": start,
                        "end": end,
                    }
                ]

        for seg in segments:
            if len(client_rows) >= MAX_EXPORT_ROWS:
                break
            therapist = (
                therapists.get(seg["therapist_user_id"])
                if seg.get("therapist_user_id")
                else None
            )
            seg_sessions = _sessions_for_segment(
                month_sessions, case.id, seg["start"], seg["end"]
            )
            st = _stats_from_sessions(seg_sessions)
            metrics = _billable_metrics_from_sessions(
                case, seg_sessions, absence_by_session
            )
            conducted = st.get("completed", 0)
            scheduled = st.get("scheduled", conducted)
            missing = _missing_logs_from_sessions(seg_sessions)
            logs_submitted = max(conducted - missing, 0)
            pending = missing
            hours = _hours_from_sessions(seg_sessions)

            client_rows.append(
                {
                    **case_people_export_fields(
                        case, therapist=therapist, parent_info=parent_info
                    ),
                    "Assignment Start": seg["start"].isoformat(),
                    "Assignment End": seg["end"].isoformat(),
                    "Service Type": case.service_type or case.product_module or "",
                    "Scheduled Sessions": scheduled,
                    "Sessions Conducted": conducted,
                    "Approved Sessions": metrics.get("approved_sessions", 0),
                    "Approved Child Absence (Billable)": metrics.get(
                        "approved_child_absence", 0
                    ),
                    "Child Absence / Parent Cancelled": st.get("client_absent", 0)
                    + st.get("cancelled", 0),
                    "Pending Logs For Review": pending,
                    "Monthly Report Submitted": (
                        "Yes" if monthly_report_submitted(db, case.id, ym) else "No"
                    ),
                    "Billable Sessions": metrics.get("billable_sessions", 0),
                }
            )

            if therapist:
                agg = therapist_agg[therapist.id]
                agg["therapist"] = therapist
                agg["mentor"] = mentor_for_therapist(db, therapist.id)
                agg["scheduled"] += scheduled
                agg["conducted"] += conducted
                agg["logs_submitted"] += logs_submitted
                agg["pending_logs"] += pending
                agg["child_absence"] += st.get("client_absent", 0)
                agg["therapist_leave"] += st.get("therapist_leave", 0)
                agg["cancelled"] += st.get("cancelled", 0)
                agg["rescheduled"] += st.get("rescheduled", 0)
                agg["billable"] += metrics.get("billable_sessions", 0)
                agg["hours"] += hours
                agg["active_clients"].add(case.id)

    therapist_rows: list[dict[str, Any]] = []
    for _tid, agg in therapist_agg.items():
        therapist = agg["therapist"]
        conducted = agg["conducted"]
        compliance = f"{round((agg['logs_submitted'] / conducted) * 100, 1)}%" if conducted else ""
        cm_names = set()
        for case in cases:
            if case.id in agg["active_clients"]:
                cm = case_manager(db, case)
                if cm:
                    cm_names.add(user_display_name(cm))
        therapist_rows.append(
            {
                "Therapist Name": user_display_name(therapist),
                "Therapist ID": export_therapist_id(therapist),
                "Mentor": user_display_name(agg.get("mentor")),
                "Case Manager": ", ".join(sorted(cm_names)),
                "Active Clients": len(agg["active_clients"]),
                "Total Scheduled Sessions": agg["scheduled"],
                "Sessions Conducted": conducted,
                "Session Logs Submitted": agg["logs_submitted"],
                "Pending Logs": agg["pending_logs"],
                "Submission Compliance": compliance,
                "Child Absence": agg["child_absence"],
                "Therapist Leave": agg["therapist_leave"],
                "Parent Cancelled": agg["cancelled"],
                "Rescheduled": agg["rescheduled"],
                "Billable Sessions": agg["billable"],
                "Total Hours Delivered": round(agg["hours"], 2),
            }
        )
    therapist_rows.sort(key=lambda r: r["Therapist Name"])
    return client_rows, therapist_rows


def replacement_history_rows(
    db: Session,
    ym: str,
    *,
    user: User | None = None,
    product_module: str | None = None,
) -> list[dict[str, Any]]:
    start, end = month_bounds(ym)
    month_label = month_long_label(ym)

    stmt = (
        select(CaseAssignment)
        .join(Case, CaseAssignment.case_id == Case.id)
        .where(
            CaseAssignment.status.in_(
                [CaseAssignmentStatus.ENDED, CaseAssignmentStatus.TRANSFERRED]
            ),
            CaseAssignment.end_date.isnot(None),
            CaseAssignment.end_date >= start,
            CaseAssignment.end_date <= end,
        )
        .order_by(CaseAssignment.end_date.desc())
    )
    if product_module:
        stmt = stmt.where(Case.product_module == product_module)

    ended = db.scalars(stmt.limit(MAX_EXPORT_ROWS)).all()
    replacement_count: dict[int, int] = defaultdict(int)
    case_cache = cases_by_ids(db, {assign.case_id for assign in ended})
    parents = parent_by_child(
        db, {c.child_id for c in case_cache.values() if c and c.child_id}
    )
    rows: list[dict[str, Any]] = []

    for assign in ended:
        case = case_cache.get(assign.case_id)
        if not case or not _case_allowed(db, user, case):
            continue
        prev_therapist = db.get(User, assign.therapist_user_id)
        new_assign = db.scalars(
            select(CaseAssignment)
            .where(
                CaseAssignment.case_id == case.id,
                CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
                CaseAssignment.start_date >= (assign.end_date or start),
            )
            .order_by(CaseAssignment.start_date.asc())
            .limit(1)
        ).first()
        new_therapist = assignment_therapist(db, new_assign)
        replacement_count[case.id] += 1
        parent_info = parents.get(case.child_id or -1, {})

        rows.append(
            {
                "Month": month_label,
                **case_people_export_fields(case, parent_info=parent_info, include_therapist=False),
                "Service Type": case.service_type or case.product_module or "",
                "Previous Therapist": user_display_name(prev_therapist),
                "Previous Therapist ID": export_therapist_id(prev_therapist),
                "Start Date": assign.start_date.isoformat(),
                "End Date": assign.end_date.isoformat() if assign.end_date else "",
                "New Therapist": user_display_name(new_therapist),
                "New Therapist ID": export_therapist_id(new_therapist),
                "Reallotted On": new_assign.start_date.isoformat() if new_assign else "",
                "Reason for Replacement": assign.reason_for_change or assign.notes or "",
                "Replacement Count": replacement_count[case.id],
                **billing_snapshot_report_columns(assign.billing_snapshot),
            }
        )
    return rows


def support_tickets_parent_rows(
    db: Session,
    ym: str,
    *,
    user: User | None = None,
    product_module: str | None = None,
) -> list[dict[str, Any]]:
    start, end = month_bounds(ym)
    month_label = month_long_label(ym)

    stmt = (
        select(SupportTicket)
        .where(
            SupportTicket.created_at >= datetime.combine(start, datetime.min.time()),
            SupportTicket.created_at <= datetime.combine(end, datetime.max.time()),
        )
        .order_by(SupportTicket.created_at.desc())
    )
    if product_module:
        stmt = stmt.where(SupportTicket.product_module == product_module)

    tickets = db.scalars(stmt.limit(MAX_EXPORT_ROWS * 2)).all()
    case_ids = {t.case_id for t in tickets if t.case_id}
    cases_by_id = cases_by_ids(db, case_ids)
    parents = parent_by_child(
        db, {c.child_id for c in cases_by_id.values() if c and c.child_id}
    )
    therapists = active_therapists_by_case(db, case_ids)
    rows: list[dict[str, Any]] = []
    for ticket in tickets:
        if not _user_has_role(db, ticket.raised_by_user_id, RoleName.PARENT.value):
            continue
        case = cases_by_id.get(ticket.case_id) if ticket.case_id else None
        if case and not _case_allowed(db, user, case):
            continue
        assignee = db.get(User, ticket.assigned_to_user_id) if ticket.assigned_to_user_id else None
        therapist = therapists.get(case.id) if case else None
        parent_info = parents.get(case.child_id, {}) if case and case.child_id else {}
        if not parent_info.get("parent_name"):
            raiser = db.get(User, ticket.raised_by_user_id)
            # Prefer full name only — do not fall back to email in Parent Name.
            if raiser and (raiser.full_name or "").strip():
                parent_info = {**parent_info, "parent_name": raiser.full_name.strip()}
        rows.append(
            {
                "Month": month_label,
                "Ticket ID": f"ST-{ticket.id}",
                **case_people_export_fields(case, therapist=therapist, parent_info=parent_info),
                "Category": enum_value(ticket.category),
                "Description": (ticket.body or ticket.subject or "")[:500],
                "Raised Date": ticket.created_at.date().isoformat() if ticket.created_at else "",
                "Assigned To": user_display_name(assignee),
                "Resolution Date": ticket.resolved_at.date().isoformat() if ticket.resolved_at else "",
                "Resolution Time": _resolution_time_label(ticket.created_at, ticket.resolved_at),
                "Status": canonical_label(
                    canonical_ticket_status(
                        ticket.status,
                        escalated_to_department=ticket.escalated_to_department,
                    )
                ),
            }
        )
        if len(rows) >= MAX_EXPORT_ROWS:
            break
    return rows


def incident_reports_rows(
    db: Session,
    ym: str,
    *,
    user: User | None = None,
    product_module: str | None = None,
    case_manager_user_id: int | list[int] | None = None,
) -> list[dict[str, Any]]:
    start, end = month_bounds(ym)
    month_label = month_long_label(ym)
    start_dt = datetime.combine(start, datetime.min.time())
    end_dt = datetime.combine(end, datetime.max.time())

    stmt = (
        select(Incident)
        .outerjoin(Case, Incident.case_id == Case.id)
        .where(
            Incident.created_at >= start_dt,
            Incident.created_at <= end_dt,
        )
        .order_by(Incident.created_at.desc())
    )
    if product_module:
        stmt = stmt.where(Case.product_module == product_module)
    stmt = apply_case_manager_filter(stmt, Case.case_manager_user_id, case_manager_user_id)

    incidents = db.scalars(stmt.limit(MAX_EXPORT_ROWS * 2)).all()
    case_ids = {i.case_id for i in incidents if i.case_id}
    cases_by_id = cases_by_ids(db, case_ids)
    parents = parent_by_child(
        db, {c.child_id for c in cases_by_id.values() if c and c.child_id}
    )
    therapists = active_therapists_by_case(db, case_ids)
    rows: list[dict[str, Any]] = []
    for incident in incidents:
        if user and not can_read_incident(db, user, incident):
            continue
        if incident.is_sensitive and user and not (
            user_has_permission(user, "incident.read_sensitive")
            or user_has_permission(user, "admin.override")
        ):
            continue
        case = cases_by_id.get(incident.case_id) if incident.case_id else None
        if case and user and not _case_allowed(db, user, case):
            continue
        reporter = db.get(User, incident.reported_by_user_id)
        assignee = db.get(User, incident.assigned_to_user_id) if incident.assigned_to_user_id else None
        cm = case_manager(db, case) if case else None
        therapist = therapists.get(case.id) if case else None
        parent_info = parents.get(case.child_id, {}) if case and case.child_id else {}
        status = normalize_incident_status(incident.status).value
        primary_category = incident.primary_category or ""
        subcategory = incident.subcategory or ""
        rows.append(
            {
                "Month": month_label,
                "Incident ID": incident.ticket_code or f"INC-{incident.id}",
                **case_people_export_fields(case, therapist=therapist, parent_info=parent_info),
                "Programme": case.product_module if case else "",
                "Category": category_label(primary_category) if primary_category else "",
                "Subcategory": subcategory_label(primary_category, subcategory)
                if primary_category and subcategory
                else subcategory,
                "Priority": enum_value(incident.priority),
                "Status": canonical_label(canonical_incident_status(status)),
                "Reported By": user_display_name(reporter),
                "Reporter Role": _reporter_role_label(reporter),
                "Assigned To": user_display_name(assignee),
                "Owner Role": incident.primary_owner_role or "",
                "Incident Date": incident.incident_at.date().isoformat() if incident.incident_at else "",
                "Reported Date": incident.created_at.date().isoformat() if incident.created_at else "",
                "Location": incident.location or "",
                "Service Type": incident.service_type or "",
                "Child Safe": incident.child_safe or "",
                "Parent Informed": incident.parent_informed or "",
                "Sensitive": "Yes" if incident.is_sensitive else "No",
                "Description": (incident.description or "")[:500],
                "Case Manager": user_display_name(cm),
            }
        )
        if len(rows) >= MAX_EXPORT_ROWS:
            break
    return rows


def cm_meetings_rows(
    db: Session,
    ym: str,
    *,
    user: User | None = None,
    product_module: str | None = None,
    case_manager_user_id: int | list[int] | None = None,
) -> tuple[list[dict], list[dict]]:
    start, end = month_bounds(ym)
    month_label = month_long_label(ym)

    checklist_types = {
        MeetingType.OBSERVATION_CHECKLIST_REVIEW,
        MeetingType.OBSERVATION_REVIEW,
    }
    iep_types = {MeetingType.IEP_MEETING}

    stmt = (
        select(CaseManagerMeeting)
        .outerjoin(Case, CaseManagerMeeting.case_id == Case.id)
        .where(
            CaseManagerMeeting.scheduled_date >= start,
            CaseManagerMeeting.scheduled_date <= end,
            CaseManagerMeeting.status == MeetingStatus.COMPLETED,
        )
        .order_by(CaseManagerMeeting.scheduled_date.desc())
    )
    if product_module:
        stmt = stmt.where(Case.product_module == product_module)
    stmt = apply_case_manager_filter(
        stmt, CaseManagerMeeting.case_manager_user_id, case_manager_user_id
    )

    meetings = db.scalars(stmt.limit(MAX_EXPORT_ROWS)).all()
    meeting_cases = cases_by_ids(db, {m.case_id for m in meetings if m.case_id})
    parents = parent_by_child(
        db, {c.child_id for c in meeting_cases.values() if c and c.child_id}
    )
    detail_rows: list[dict[str, Any]] = []
    summary: dict[int, dict[str, Any]] = defaultdict(
        lambda: {
            "shadow_checklist": 0,
            "homecare_checklist": 0,
            "shadow_iep": 0,
            "homecare_iep": 0,
            "therapist_escalations": 0,
            "parent_escalations": 0,
            "cm_user": None,
        }
    )

    for meeting in meetings:
        case = meeting_cases.get(meeting.case_id) if meeting.case_id else None
        if case and not _case_allowed(db, user, case):
            continue
        cm_user = db.get(User, meeting.case_manager_user_id)
        therapist = db.get(User, meeting.therapist_user_id) if meeting.therapist_user_id else None
        module = (case.product_module if case else "") or ""
        is_shadow = "shadow" in module.lower()
        is_homecare = "homecare" in module.lower()
        mtype = meeting.meeting_type

        if mtype in checklist_types:
            if is_shadow:
                summary[meeting.case_manager_user_id]["shadow_checklist"] += 1
            elif is_homecare:
                summary[meeting.case_manager_user_id]["homecare_checklist"] += 1
        if mtype in iep_types:
            if is_shadow:
                summary[meeting.case_manager_user_id]["shadow_iep"] += 1
            elif is_homecare:
                summary[meeting.case_manager_user_id]["homecare_iep"] += 1
        summary[meeting.case_manager_user_id]["cm_user"] = cm_user
        parent_info = parents.get(case.child_id, {}) if case and case.child_id else {}

        detail_rows.append(
            {
                "Date": meeting.scheduled_date.isoformat(),
                "Case Manager": user_display_name(cm_user),
                **case_people_export_fields(case, therapist=therapist, parent_info=parent_info),
                "Service Type": (case.service_type if case else "") or module,
                "Meeting Agenda": enum_value(mtype),
                "Important Notes": (meeting.notes_summary or meeting.notes_action or "")[:500],
                "IEP Submission Date": "",
                "IEP Reviewed And Sent On": "",
            }
        )

    _fill_escalation_counts(db, summary, start, end, product_module)

    summary_rows: list[dict[str, Any]] = []
    for cm_id, data in summary.items():
        cm_user = data["cm_user"] or db.get(User, cm_id)
        summary_rows.append(
            {
                "Month": month_label,
                "Case Manager": user_display_name(cm_user),
                "Shadow Checklist Done": data["shadow_checklist"],
                "Homecare Checklist Done": data["homecare_checklist"],
                "Shadow IEP Done": data["shadow_iep"],
                "Homecare IEP Done": data["homecare_iep"],
                "Escalations By Therapists": data["therapist_escalations"],
                "Escalations By Parents": data["parent_escalations"],
            }
        )
    summary_rows.sort(key=lambda r: r["Case Manager"])
    return detail_rows, summary_rows


def inactive_clients_rows(
    db: Session,
    *,
    user: User | None = None,
    product_module: str | None = None,
    case_manager_user_id: int | list[int] | None = None,
) -> list[dict[str, Any]]:
    today = today_ist()
    cases = scoped_cases(
        db,
        user,
        product_module=product_module,
        case_manager_user_id=case_manager_user_id,
        active_only=True,
    )
    rows: list[dict[str, Any]] = []
    parents = parent_by_child(db, {c.child_id for c in cases if c.child_id})
    for case in cases[:MAX_EXPORT_ROWS]:
        if not _case_allowed(db, user, case):
            continue
        last_session = last_completed_session_date(db, case.id)
        inactive_days = days_since(last_session, as_of=today)
        if last_session and inactive_days is not None and inactive_days < INACTIVE_DAYS_THRESHOLD:
            continue
        if not last_session:
            inactive_days = days_since(
                case.created_at.date() if case.created_at else None, as_of=today
            )

        assign = active_assignment(db, case.id)
        therapist = assignment_therapist(db, assign)
        cm = case_manager(db, case)
        parent_info = parents.get(case.child_id or -1, {})
        rows.append(
            {
                **case_people_export_fields(case, therapist=therapist, parent_info=parent_info),
                "Service Type": case.service_type or case.product_module or "",
                "Last Completed Session": last_session.isoformat() if last_session else "",
                "Days Inactive": inactive_days if inactive_days is not None else "",
                "Case Status": enum_value(case.status),
                "Therapist Status": _therapist_status_label(therapist),
                "Case Manager": user_display_name(cm),
            }
        )
    rows.sort(
        key=lambda r: r["Days Inactive"] if isinstance(r["Days Inactive"], int) else 0,
        reverse=True,
    )
    return rows


def _parent_portal_activity(
    db: Session, parent_user_ids: set[int]
) -> tuple[dict[int, datetime], set[int]]:
    """Last login date and users with any parent portal session (login or invite accept)."""
    if not parent_user_ids:
        return {}, set()

    login_rows = db.execute(
        select(AuditEvent.actor_user_id, func.max(AuditEvent.created_at))
        .where(
            AuditEvent.actor_user_id.in_(parent_user_ids),
            AuditEvent.action == "login",
        )
        .group_by(AuditEvent.actor_user_id)
    ).all()
    last_login_by_user = {uid: dt for uid, dt in login_rows if uid and dt}

    portal_session_rows = db.scalars(
        select(AuditEvent.actor_user_id)
        .where(
            AuditEvent.actor_user_id.in_(parent_user_ids),
            AuditEvent.action.in_(("login", "accept_invite")),
        )
        .distinct()
    ).all()
    has_portal_session = {uid for uid in portal_session_rows if uid}
    return last_login_by_user, has_portal_session


def parent_portal_usage_rows(
    db: Session,
    *,
    user: User | None = None,
    product_module: str | None = None,
    case_manager_user_id: int | list[int] | None = None,
) -> list[dict[str, Any]]:
    today = today_ist()
    cases = scoped_cases(
        db,
        user,
        product_module=product_module,
        case_manager_user_id=case_manager_user_id,
        active_only=False,
    )
    allowed_cases = [
        case
        for case in cases[:MAX_EXPORT_ROWS]
        if _case_allowed(db, user, case)
        and enum_value(case.status) not in _TERMINAL_CASE_STATUSES
    ]
    child_ids = {case.child_id for case in allowed_cases if case.child_id}
    parents = parent_by_child(db, child_ids)
    therapists = active_therapists_by_case(db, {case.id for case in allowed_cases})
    parent_user_ids = {
        info["user_id"] for info in parents.values() if info.get("user_id")
    }
    last_login_by_user, has_portal_session = _parent_portal_activity(db, parent_user_ids)

    rows: list[dict[str, Any]] = []
    for case in allowed_cases:
        parent = parents.get(case.child_id or -1, {})
        parent_user_id = parent.get("user_id")
        last_login = last_login_by_user.get(parent_user_id) if parent_user_id else None
        is_active = bool(parent_user_id and parent_user_id in has_portal_session)
        days_since_activity = (
            days_since(last_login.date() if last_login else None, as_of=today)
            if last_login
            else None
        )
        cm = case_manager(db, case)
        therapist = therapists.get(case.id)
        rows.append(
            {
                **case_people_export_fields(case, therapist=therapist, parent_info=parent),
                "Login Status": "Active" if is_active else "Inactive",
                "Last Login": last_login.date().isoformat() if last_login else "",
                "Days Since Last Login": days_since_activity
                if days_since_activity is not None
                else "",
                "Case Status": enum_value(case.status),
                "Case Manager": user_display_name(cm),
            }
        )
    rows.sort(
        key=lambda r: (
            r["Days Since Last Login"]
            if isinstance(r["Days Since Last Login"], int)
            else -1
        ),
        reverse=True,
    )
    return rows


def therapist_log_compliance_rows(
    db: Session,
    *,
    user: User | None = None,
    product_module: str | None = None,
    case_manager_user_id: int | list[int] | None = None,
) -> list[dict[str, Any]]:
    """One row per therapist–case pair with completed sessions missing logs (2+ days old)."""
    today = today_ist()
    cutoff = today - timedelta(days=THERAPIST_LOG_COMPLIANCE_MIN_AGE_DAYS)

    cases = scoped_cases(
        db,
        user,
        product_module=product_module,
        case_manager_user_id=case_manager_user_id,
        active_only=True,
    )
    cases_by_id = {c.id: c for c in cases if _case_allowed(db, user, c)}
    case_ids = list(cases_by_id.keys())
    if not case_ids:
        return []

    therapist_ids = list(
        {
            int(therapist_id)
            for therapist_id, _case_id in db.execute(
                select(CaseAssignment.therapist_user_id, CaseAssignment.case_id).where(
                    CaseAssignment.case_id.in_(case_ids),
                    CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
                )
            ).all()
        }
    )
    if not therapist_ids:
        return []

    missing_rows = db.execute(
        select(
            TherapySession.therapist_user_id,
            TherapySession.case_id,
            TherapySession.scheduled_date,
        )
        .outerjoin(DailyLog, DailyLog.session_id == TherapySession.id)
        .where(
            TherapySession.therapist_user_id.in_(therapist_ids),
            TherapySession.case_id.in_(case_ids),
            TherapySession.status == SessionStatus.COMPLETED,
            DailyLog.id.is_(None),
            TherapySession.scheduled_date <= cutoff,
        )
        .order_by(TherapySession.therapist_user_id, TherapySession.case_id, TherapySession.scheduled_date)
    ).all()

    missing_by_pair: dict[tuple[int, int], list[date]] = defaultdict(list)
    for therapist_id, case_id, scheduled_date in missing_rows:
        missing_by_pair[(int(therapist_id), int(case_id))].append(scheduled_date)

    if not missing_by_pair:
        return []

    last_submitted = {
        (int(therapist_id), int(case_id)): submitted_at
        for therapist_id, case_id, submitted_at in db.execute(
            select(
                TherapySession.therapist_user_id,
                TherapySession.case_id,
                func.max(DailyLog.submitted_at),
            )
            .join(DailyLog, DailyLog.session_id == TherapySession.id)
            .where(
                TherapySession.therapist_user_id.in_(therapist_ids),
                TherapySession.case_id.in_(case_ids),
                DailyLog.submitted_at.isnot(None),
            )
            .group_by(TherapySession.therapist_user_id, TherapySession.case_id)
        ).all()
        if submitted_at
    }

    out: list[dict[str, Any]] = []
    parents = parent_by_child(
        db, {cases_by_id[cid].child_id for (_, cid) in missing_by_pair if cases_by_id.get(cid) and cases_by_id[cid].child_id}
    )
    for (therapist_id, case_id), missing_dates in missing_by_pair.items():
        case = cases_by_id.get(case_id)
        if not case:
            continue
        therapist = db.get(User, therapist_id)
        oldest = min(missing_dates)
        newest = max(missing_dates)
        last_at = last_submitted.get((therapist_id, case_id))
        cm = case_manager(db, case)
        parent_info = parents.get(case.child_id or -1, {})

        out.append(
            {
                **case_people_export_fields(case, therapist=therapist, parent_info=parent_info),
                "Mentor": user_display_name(mentor_for_therapist(db, therapist_id)),
                "Case Manager": user_display_name(cm),
                "Missing Logs": len(missing_dates),
                "Not Submitting Since": oldest.isoformat(),
                "Days Since Oldest Missing": days_since(oldest, as_of=today),
                "Newest Missing Session Date": newest.isoformat(),
                "Last Log Submitted": last_at.date().isoformat() if last_at else "",
            }
        )

    out.sort(
        key=lambda r: (
            r["Days Since Oldest Missing"] if isinstance(r["Days Since Oldest Missing"], int) else 0
        ),
        reverse=True,
    )
    return out[:MAX_EXPORT_ROWS]


def _load_sessions_in_range(
    db: Session, case_ids: list[int], start: date, end: date
) -> list[TherapySession]:
    if not case_ids:
        return []
    return list(
        db.scalars(
            select(TherapySession)
            .options(selectinload(TherapySession.daily_log))
            .where(
                TherapySession.case_id.in_(case_ids),
                TherapySession.scheduled_date >= start,
                TherapySession.scheduled_date <= end,
            )
        ).all()
    )


def _sessions_for_segment(
    sessions: list[TherapySession],
    case_id: int,
    seg_start: date,
    seg_end: date,
) -> list[TherapySession]:
    return [
        s
        for s in sessions
        if s.case_id == case_id and seg_start <= s.scheduled_date <= seg_end
    ]


def _stats_from_sessions(sessions: list[TherapySession]) -> dict[str, int]:
    stats: dict[str, int] = defaultdict(int)
    status_map = {
        SessionStatus.COMPLETED: "completed",
        SessionStatus.CLIENT_ABSENT: "client_absent",
        SessionStatus.THERAPIST_LEAVE: "therapist_leave",
        SessionStatus.CANCELLED: "cancelled",
        SessionStatus.RESCHEDULED: "rescheduled",
    }
    for s in sessions:
        stats["scheduled"] += 1
        key = status_map.get(s.status)
        if key:
            stats[key] += 1
    return dict(stats)


def _missing_logs_from_sessions(sessions: list[TherapySession]) -> int:
    return sum(
        1
        for s in sessions
        if s.status == SessionStatus.COMPLETED and s.daily_log is None
    )


def _log_gaps_from_sessions(sessions: list[TherapySession]) -> tuple[int, int]:
    pending = 0
    rejected = 0
    for s in sessions:
        if s.status != SessionStatus.COMPLETED or not s.daily_log:
            continue
        status = s.daily_log.approval_status
        value = status.value if hasattr(status, "value") else status
        if value == LogApprovalStatus.PENDING.value:
            pending += 1
        elif value == LogApprovalStatus.REJECTED.value:
            rejected += 1
    return pending, rejected


def _hours_from_sessions(sessions: list[TherapySession]) -> float:
    hours = 0.0
    for s in sessions:
        if s.status != SessionStatus.COMPLETED:
            continue
        mins = 0
        if s.actual_start_at and s.actual_end_at:
            mins = int((s.actual_end_at - s.actual_start_at).total_seconds() / 60)
        elif s.start_time and s.end_time:
            start_dt = datetime.combine(s.scheduled_date, s.start_time)
            end_dt = datetime.combine(s.scheduled_date, s.end_time)
            mins = int((end_dt - start_dt).total_seconds() / 60)
        hours += mins / 60.0
    return hours


def _billable_metrics_from_sessions(
    case: Case,
    sessions: list[TherapySession],
    absence_by_session: dict[int, dict[str, str]],
) -> dict[str, int]:
    approved = 0
    approved_child_absence = 0
    for s in sessions:
        if s.status == SessionStatus.COMPLETED and s.daily_log:
            status = s.daily_log.approval_status
            value = status.value if hasattr(status, "value") else status
            if value == LogApprovalStatus.APPROVED.value:
                approved += 1
        if s.status == SessionStatus.CLIENT_ABSENT:
            absence = absence_by_session.get(s.id) or {}
            if (
                absence.get("status") == SessionAbsenceStatus.APPROVED.value
                and absence.get("type") == SessionAbsenceType.CLIENT_ABSENT.value
            ):
                approved_child_absence += 1
    if is_homecare_case(case):
        billable = approved
    else:
        billable = approved + approved_child_absence
    return {
        "approved_sessions": approved,
        "approved_child_absence": approved_child_absence,
        "billable_sessions": billable,
    }


def _session_stats_by_case(db: Session, case_ids: list[int], ym: str) -> dict[int, dict[str, int]]:
    if not case_ids:
        return {}
    year_s, month_s = ym.split("-")[:2]
    y, m = int(year_s), int(month_s)
    stats: dict[int, dict[str, int]] = {cid: defaultdict(int) for cid in case_ids}

    rows = db.execute(
        select(TherapySession.case_id, TherapySession.status, func.count())
        .where(
            TherapySession.case_id.in_(case_ids),
            extract("year", TherapySession.scheduled_date) == y,
            extract("month", TherapySession.scheduled_date) == m,
        )
        .group_by(TherapySession.case_id, TherapySession.status)
    ).all()
    status_map = {
        SessionStatus.COMPLETED: "completed",
        SessionStatus.CLIENT_ABSENT: "client_absent",
        SessionStatus.THERAPIST_LEAVE: "therapist_leave",
        SessionStatus.CANCELLED: "cancelled",
        SessionStatus.RESCHEDULED: "rescheduled",
    }
    for case_id, status, cnt in rows:
        stats[case_id]["scheduled"] += int(cnt)
        key = status_map.get(status)
        if key:
            stats[case_id][key] = int(cnt)

    return {k: dict(v) for k, v in stats.items()}


def _approved_sessions_by_case(
    db: Session, case_ids: list[int], start: date, end: date
) -> dict[int, int]:
    if not case_ids:
        return {}
    return dict(
        db.execute(
            select(TherapySession.case_id, func.count())
            .join(DailyLog, DailyLog.session_id == TherapySession.id)
            .where(
                TherapySession.case_id.in_(case_ids),
                TherapySession.status == SessionStatus.COMPLETED,
                TherapySession.scheduled_date >= start,
                TherapySession.scheduled_date <= end,
                DailyLog.approval_status == LogApprovalStatus.APPROVED.value,
            )
            .group_by(TherapySession.case_id)
        ).all()
    )


def _approved_child_absence_billable_by_case(
    db: Session, case_ids: list[int], start: date, end: date
) -> dict[int, int]:
    if not case_ids:
        return {}
    return dict(
        db.execute(
            select(TherapySession.case_id, func.count())
            .join(
                SessionAbsenceRequest,
                SessionAbsenceRequest.session_id == TherapySession.id,
            )
            .where(
                TherapySession.case_id.in_(case_ids),
                TherapySession.status == SessionStatus.CLIENT_ABSENT,
                TherapySession.scheduled_date >= start,
                TherapySession.scheduled_date <= end,
                SessionAbsenceRequest.status == SessionAbsenceStatus.APPROVED,
                SessionAbsenceRequest.absence_type == SessionAbsenceType.CLIENT_ABSENT,
            )
            .group_by(TherapySession.case_id)
        ).all()
    )


def _log_approval_gap_by_case(
    db: Session, case_ids: list[int], start: date, end: date
) -> tuple[dict[int, int], dict[int, int]]:
    """Completed sessions with submitted logs awaiting approval or rejected."""
    if not case_ids:
        return {}, {}
    pending: dict[int, int] = {}
    rejected: dict[int, int] = {}
    rows = db.execute(
        select(TherapySession.case_id, DailyLog.approval_status, func.count())
        .join(DailyLog, DailyLog.session_id == TherapySession.id)
        .where(
            TherapySession.case_id.in_(case_ids),
            TherapySession.status == SessionStatus.COMPLETED,
            TherapySession.scheduled_date >= start,
            TherapySession.scheduled_date <= end,
            DailyLog.approval_status.in_(
                (LogApprovalStatus.PENDING.value, LogApprovalStatus.REJECTED.value)
            ),
        )
        .group_by(TherapySession.case_id, DailyLog.approval_status)
    ).all()
    for case_id, approval_status, cnt in rows:
        if approval_status == LogApprovalStatus.PENDING.value:
            pending[case_id] = int(cnt)
        elif approval_status == LogApprovalStatus.REJECTED.value:
            rejected[case_id] = int(cnt)
    return pending, rejected


def _build_billable_metrics(
    db: Session,
    cases: list[Case],
    case_ids: list[int],
    start: date,
    end: date,
) -> dict[int, dict[str, Any]]:
    approved_sessions = _approved_sessions_by_case(db, case_ids, start, end)
    approved_child_absence = _approved_child_absence_billable_by_case(db, case_ids, start, end)
    cases_by_id = {c.id: c for c in cases if c.id in case_ids}
    out: dict[int, dict[str, Any]] = {}

    for case_id in case_ids:
        case = cases_by_id.get(case_id)
        approved = int(approved_sessions.get(case_id, 0))
        child_absence = int(approved_child_absence.get(case_id, 0))

        if case and is_homecare_case(case):
            billable = approved
        elif case and is_shadow_case(case):
            billable = approved + child_absence
        else:
            billable = approved + child_absence

        out[case_id] = {
            "approved_sessions": approved,
            "approved_child_absence": child_absence,
            "billable_sessions": billable,
        }
    return out


def _session_billable_label(
    case: Case | None,
    session: TherapySession,
    log: DailyLog | None,
    absence: dict[str, str] | None,
    ledger_label: str,
) -> str:
    if case and is_homecare_case(case):
        if session.status == SessionStatus.COMPLETED and log:
            if log.approval_status == LogApprovalStatus.APPROVED.value:
                return "Yes"
            return "No"
        if session.status == SessionStatus.CLIENT_ABSENT and absence:
            if absence.get("status") == SessionAbsenceStatus.APPROVED.value:
                return "Yes"
            return "No"
        return "No"
    return ledger_label or "No"


def _missing_logs_in_month(
    db: Session, case_ids: list[int], start: date, end: date
) -> dict[int, int]:
    if not case_ids:
        return {}
    return dict(
        db.execute(
            select(TherapySession.case_id, func.count())
            .outerjoin(DailyLog, DailyLog.session_id == TherapySession.id)
            .where(
                TherapySession.case_id.in_(case_ids),
                TherapySession.status == SessionStatus.COMPLETED,
                TherapySession.scheduled_date >= start,
                TherapySession.scheduled_date <= end,
                DailyLog.id.is_(None),
            )
            .group_by(TherapySession.case_id)
        ).all()
    )


def _session_hours_by_case(db: Session, case_ids: list[int], ym: str) -> dict[int, float]:
    if not case_ids:
        return {}
    year_s, month_s = ym.split("-")[:2]
    y, m = int(year_s), int(month_s)
    sessions = db.scalars(
        select(TherapySession).where(
            TherapySession.case_id.in_(case_ids),
            TherapySession.status == SessionStatus.COMPLETED,
            extract("year", TherapySession.scheduled_date) == y,
            extract("month", TherapySession.scheduled_date) == m,
        )
    ).all()
    hours: dict[int, float] = defaultdict(float)
    for s in sessions:
        mins = 0
        if s.actual_start_at and s.actual_end_at:
            mins = int((s.actual_end_at - s.actual_start_at).total_seconds() / 60)
        elif s.start_time and s.end_time:
            start_dt = datetime.combine(s.scheduled_date, s.start_time)
            end_dt = datetime.combine(s.scheduled_date, s.end_time)
            mins = int((end_dt - start_dt).total_seconds() / 60)
        hours[s.case_id] += mins / 60.0
    return dict(hours)


def _absence_by_session(db: Session, session_ids: list[int]) -> dict[int, dict[str, str]]:
    if not session_ids:
        return {}
    rows = db.scalars(
        select(SessionAbsenceRequest).where(SessionAbsenceRequest.session_id.in_(session_ids))
    ).all()
    return {row.session_id: {"status": enum_value(row.status), "type": enum_value(row.absence_type)} for row in rows}


def _billable_by_session(db: Session, session_ids: list[int]) -> dict[int, str]:
    if not session_ids:
        return {}
    rows = db.execute(
        select(BillingLedger.session_id, BillingLedger.billable_status).where(
            BillingLedger.session_id.in_(session_ids)
        )
    ).all()
    return {sid: enum_value(status) for sid, status in rows if sid}


def _fill_escalation_counts(
    db: Session,
    summary: dict[int, dict[str, Any]],
    start: date,
    end: date,
    product_module: str | None,
) -> None:
    start_dt = datetime.combine(start, datetime.min.time())
    end_dt = datetime.combine(end, datetime.max.time())

    ticket_stmt = select(SupportTicket).where(
        SupportTicket.created_at >= start_dt,
        SupportTicket.created_at <= end_dt,
        SupportTicket.case_id.isnot(None),
    )
    if product_module:
        ticket_stmt = ticket_stmt.where(SupportTicket.product_module == product_module)
    for ticket in db.scalars(ticket_stmt).all():
        case = case_service.get_case(db, ticket.case_id) if ticket.case_id else None
        if not case or not case.case_manager_user_id:
            continue
        cm_id = case.case_manager_user_id
        if cm_id not in summary:
            summary[cm_id]["cm_user"] = db.get(User, cm_id)
        if _user_has_role(db, ticket.raised_by_user_id, RoleName.PARENT.value):
            summary[cm_id]["parent_escalations"] += 1
        elif _user_has_role(db, ticket.raised_by_user_id, RoleName.THERAPIST.value):
            summary[cm_id]["therapist_escalations"] += 1

    incident_stmt = select(Incident).where(
        Incident.case_id.isnot(None),
        Incident.created_at >= start_dt,
        Incident.created_at <= end_dt,
    )
    for inc in db.scalars(incident_stmt).all():
        case = case_service.get_case(db, inc.case_id) if inc.case_id else None
        if not case or not case.case_manager_user_id:
            continue
        cm_id = case.case_manager_user_id
        if cm_id not in summary:
            summary[cm_id]["cm_user"] = db.get(User, cm_id)
        reporter = db.get(User, inc.reported_by_user_id)
        if reporter and RoleName.THERAPIST.value in (reporter.role_names or []):
            summary[cm_id]["therapist_escalations"] += 1
        elif reporter and RoleName.PARENT.value in (reporter.role_names or []):
            summary[cm_id]["parent_escalations"] += 1
