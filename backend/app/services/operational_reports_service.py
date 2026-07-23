"""Operational report queries for HR / admin exports."""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any, Optional

from app.core.timezone import today_ist

from sqlalchemy import extract, func, select
from sqlalchemy.orm import Session, selectinload

from app.core.permissions import RoleName, case_scope_check
from app.models.assignment import CaseAssignment, CaseAssignmentStatus
from app.models.case import Case, CaseStatus
from app.models.case_manager_meeting import CaseManagerMeeting, MeetingStatus, MeetingType
from app.models.daily_log import DailyLog, LogApprovalStatus
from app.models.incident import Incident
from app.models.ledger_billing import BillableStatus, BillingLedger
from app.models.session import Session as TherapySession
from app.models.session import SessionStatus
from app.models.session_absence import SessionAbsenceRequest, SessionAbsenceStatus, SessionAbsenceType
from app.models.app_usage_chunk import AppUsageChunk
from app.models.audit_event import AuditEvent
from app.models.parent import ParentGuardian, parent_child_link
from app.models.support_ticket import SupportTicket
from app.models.user import User
from app.services import case_service, leave_policy_service
from app.services.user_provision_service import login_ready
from app.services.reports_export_helpers import (
    INACTIVE_DAYS_THRESHOLD,
    MAX_EXPORT_ROWS,
    active_assignment,
    assignment_therapist,
    calendar_days_in_month,
    case_manager,
    days_since,
    enum_value,
    export_case_id,
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
    parse_iso_date,
    scoped_cases,
    shadow_leave_deduction_estimate,
    shadow_per_session_day_rate,
    THERAPIST_LOG_COMPLIANCE_MIN_AGE_DAYS,
    user_display_name,
)


def _case_allowed(db: Session, user: User | None, case: Case | None) -> bool:
    if not case or not user:
        return True
    return case_scope_check(db, user, case)


def _user_has_role(db: Session, user_id: int, role_name: str) -> bool:
    user = db.get(User, user_id)
    if not user:
        return False
    return role_name in (user.role_names or [])


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
    case_manager_user_id: int | None = None,
    therapist_user_id: int | None = None,
    case_id: int | None = None,
) -> dict[str, Any]:
    ym = normalize_month(month)
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
    case_manager_user_id: int | None = None,
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

    session_stats = _session_stats_by_case(db, case_ids, ym)
    billable_metrics = _build_billable_metrics(
        db, cases, case_ids, ym, start, end, session_stats, leave_cache={}
    )
    missing_logs_month = _missing_logs_in_month(db, case_ids, start, end)
    hours_by_case = _session_hours_by_case(db, case_ids, ym)

    rows: list[dict[str, Any]] = []
    for case in cases[:MAX_EXPORT_ROWS]:
        if not _case_allowed(db, user, case):
            continue
        assign = active_assignment(db, case.id)
        therapist = assignment_therapist(db, assign)
        if not therapist:
            continue
        stats = session_stats.get(case.id, {})
        leave = leave_days_in_month(db, therapist.id, ym)
        balance = leave_policy_service.get_leave_balance(db, therapist, year=year, as_of=end)
        cm = case_manager(db, case)
        metrics = billable_metrics.get(case.id, {})

        rows.append(
            {
                "Month": month_label,
                "Case ID": export_case_id(case),
                "Client Name": case_service.case_child_display_name(case) or "",
                "Therapist Name": user_display_name(therapist),
                "Therapist ID": export_therapist_id(therapist),
                "Service Type": case.service_type or case.product_module or "",
                "Case Manager": user_display_name(cm),
                "Total Calendar Days": cal_days,
                "Scheduled Sessions": stats.get("scheduled", 0),
                "Sessions Completed": stats.get("completed", 0),
                "Approved Sessions": metrics.get("approved_sessions", 0),
                "Approved Child Absence (Billable)": metrics.get("approved_child_absence", 0),
                "Child Absence (All)": stats.get("client_absent", 0),
                "Therapist Leave": stats.get("therapist_leave", 0),
                "Parent Cancelled": stats.get("cancelled", 0),
                "Rescheduled": stats.get("rescheduled", 0),
                "Completed Missing Logs": missing_logs_month.get(case.id, 0),
                "Leave Paid Days": leave["paid"],
                "Leave Unpaid Days": leave["unpaid"],
                "Leave Credits Remaining": balance.get("leave_credit_pending", balance.get("paid_remaining", 0)),
                "Total Session Hours": round(hours_by_case.get(case.id, 0), 2),
                "Billable Sessions": metrics.get("billable_sessions", 0),
                "Monthly Fixed Pay": metrics.get("monthly_fixed_pay", ""),
                "Per Session Day Rate": metrics.get("per_session_day_rate", ""),
                "Estimated Unpaid Leave Deduction": metrics.get("leave_deduction_estimate", ""),
                "Monthly Report Submitted": "Yes" if monthly_report_submitted(db, case.id, ym) else "No",
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
    case_manager_user_id: int | None = None,
    therapist_user_id: int | None = None,
    case_id: int | None = None,
) -> list[dict[str, Any]]:
    today = date.today()
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
    if case_manager_user_id:
        stmt = stmt.where(Case.case_manager_user_id == case_manager_user_id)
    if therapist_user_id:
        stmt = stmt.where(TherapySession.therapist_user_id == therapist_user_id)
    if case_id:
        stmt = stmt.where(TherapySession.case_id == case_id)

    sessions = db.scalars(stmt.limit(MAX_EXPORT_ROWS)).all()
    absence_by_session = _absence_by_session(db, [s.id for s in sessions])
    billable_by_session = _billable_by_session(db, [s.id for s in sessions])

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
                "Case ID": export_case_id(case),
                "Client Name": case_service.case_child_display_name(case) if case else "",
                "Therapist Name": user_display_name(therapist),
                "Therapist ID": export_therapist_id(therapist),
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
    case_manager_user_id: int | None = None,
) -> tuple[list[dict], list[dict]]:
    cases = scoped_cases(
        db,
        user,
        product_module=product_module,
        case_manager_user_id=case_manager_user_id,
    )
    case_ids = [c.id for c in cases if _case_allowed(db, user, c)]
    stats = _session_stats_by_case(db, case_ids, ym)
    start, end = month_bounds(ym)
    billable_metrics = _build_billable_metrics(db, cases, case_ids, ym, start, end, stats, leave_cache={})
    missing_logs = _missing_logs_in_month(db, case_ids, start, end)
    hours = _session_hours_by_case(db, case_ids, ym)

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

    for case in cases[:MAX_EXPORT_ROWS]:
        if case.id not in case_ids:
            continue
        assign = active_assignment(db, case.id)
        therapist = assignment_therapist(db, assign)
        st = stats.get(case.id, {})
        metrics = billable_metrics.get(case.id, {})
        conducted = st.get("completed", 0)
        scheduled = st.get("scheduled", conducted)
        logs_submitted = max(conducted - missing_logs.get(case.id, 0), 0)
        pending = missing_logs.get(case.id, 0)

        client_rows.append(
            {
                "Case ID": export_case_id(case),
                "Client Name": case_service.case_child_display_name(case) or "",
                "Therapist Name": user_display_name(therapist),
                "Therapist ID": export_therapist_id(therapist),
                "Service Type": case.service_type or case.product_module or "",
                "Scheduled Sessions": scheduled,
                "Sessions Conducted": conducted,
                "Approved Sessions": metrics.get("approved_sessions", 0),
                "Approved Child Absence (Billable)": metrics.get("approved_child_absence", 0),
                "Child Absence / Parent Cancelled": st.get("client_absent", 0) + st.get("cancelled", 0),
                "Pending Logs For Review": pending,
                "Monthly Report Submitted": "Yes" if monthly_report_submitted(db, case.id, ym) else "No",
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
            agg["hours"] += hours.get(case.id, 0)
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
    rows: list[dict[str, Any]] = []

    for assign in ended:
        case = db.get(Case, assign.case_id)
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

        rows.append(
            {
                "Month": month_label,
                "Case ID": export_case_id(case),
                "Client Name": case_service.case_child_display_name(case) or "",
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
    rows: list[dict[str, Any]] = []
    for ticket in tickets:
        if not _user_has_role(db, ticket.raised_by_user_id, RoleName.PARENT.value):
            continue
        case = case_service.get_case(db, ticket.case_id) if ticket.case_id else None
        if case and not _case_allowed(db, user, case):
            continue
        assignee = db.get(User, ticket.assigned_to_user_id) if ticket.assigned_to_user_id else None
        rows.append(
            {
                "Month": month_label,
                "Ticket ID": f"ST-{ticket.id}",
                "Case ID": export_case_id(case) if case else "",
                "Client Name": case_service.case_child_display_name(case) if case else "",
                "Category": enum_value(ticket.category),
                "Description": (ticket.body or ticket.subject or "")[:500],
                "Raised Date": ticket.created_at.date().isoformat() if ticket.created_at else "",
                "Assigned To": user_display_name(assignee),
                "Resolution Date": ticket.resolved_at.date().isoformat() if ticket.resolved_at else "",
                "Resolution Time": _resolution_time_label(ticket.created_at, ticket.resolved_at),
                "Status": enum_value(ticket.status),
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
    case_manager_user_id: int | None = None,
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
    if case_manager_user_id:
        stmt = stmt.where(CaseManagerMeeting.case_manager_user_id == case_manager_user_id)

    meetings = db.scalars(stmt.limit(MAX_EXPORT_ROWS)).all()
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
        case = db.get(Case, meeting.case_id) if meeting.case_id else None
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

        detail_rows.append(
            {
                "Date": meeting.scheduled_date.isoformat(),
                "Case Manager": user_display_name(cm_user),
                "Therapist Name": user_display_name(therapist),
                "Therapist ID": export_therapist_id(therapist),
                "Case ID": export_case_id(case),
                "Client Name": case_service.case_child_display_name(case) if case else "",
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
    case_manager_user_id: int | None = None,
) -> list[dict[str, Any]]:
    today = date.today()
    cases = scoped_cases(
        db,
        user,
        product_module=product_module,
        case_manager_user_id=case_manager_user_id,
        active_only=True,
    )
    rows: list[dict[str, Any]] = []
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
        rows.append(
            {
                "Case ID": export_case_id(case),
                "Client Name": case_service.case_child_display_name(case) or "",
                "Service Type": case.service_type or case.product_module or "",
                "Therapist Name": user_display_name(therapist),
                "Therapist ID": export_therapist_id(therapist),
                "Last Completed Session": last_session.isoformat() if last_session else "",
                "Days Inactive": inactive_days if inactive_days is not None else "",
                "Case Manager": user_display_name(cm),
            }
        )
    rows.sort(
        key=lambda r: r["Days Inactive"] if isinstance(r["Days Inactive"], int) else 0,
        reverse=True,
    )
    return rows


def _parent_by_child(db: Session, child_ids: set[int]) -> dict[int, dict[str, Any]]:
    if not child_ids:
        return {}
    rows = db.execute(
        select(
            parent_child_link.c.child_id,
            User.id,
            User.full_name,
            User.email,
            User.is_active,
            User.password_hash,
        )
        .join(ParentGuardian, ParentGuardian.id == parent_child_link.c.parent_guardian_id)
        .join(User, User.id == ParentGuardian.user_id)
        .where(parent_child_link.c.child_id.in_(child_ids))
        .order_by(parent_child_link.c.child_id, ParentGuardian.id)
    ).all()
    out: dict[int, dict[str, Any]] = {}
    for child_id, user_id, full_name, email, is_active, password_hash in rows:
        if child_id in out:
            continue
        parent_user = User(
            id=user_id,
            email=email or "",
            full_name=full_name,
            is_active=is_active,
            password_hash=password_hash,
        )
        out[child_id] = {
            "user_id": user_id,
            "parent_name": full_name or "",
            "parent_email": email or "",
            "login_ready": login_ready(parent_user, db),
        }
    return out


def _parent_portal_activity(db: Session, parent_user_ids: set[int]) -> tuple[dict[int, datetime], set[int], dict[int, datetime]]:
    """Last login, users with any portal session, and last parent-portal heartbeat."""
    if not parent_user_ids:
        return {}, set(), {}

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

    seen_rows = db.execute(
        select(AppUsageChunk.actor_user_id, func.max(AppUsageChunk.chunk_ended_at))
        .where(
            AppUsageChunk.actor_user_id.in_(parent_user_ids),
            AppUsageChunk.portal == "parent",
        )
        .group_by(AppUsageChunk.actor_user_id)
    ).all()
    last_seen_by_user = {uid: dt for uid, dt in seen_rows if uid and dt}
    return last_login_by_user, has_portal_session, last_seen_by_user


def _latest_activity_date(
    last_login: datetime | None,
    last_seen: datetime | None,
) -> date | None:
    candidates: list[date] = []
    for dt in (last_login, last_seen):
        if not dt:
            continue
        candidates.append(dt.date() if isinstance(dt, datetime) else dt)
    return max(candidates) if candidates else None


def parent_portal_usage_rows(
    db: Session,
    *,
    user: User | None = None,
    product_module: str | None = None,
    case_manager_user_id: int | None = None,
) -> list[dict[str, Any]]:
    today = date.today()
    cases = scoped_cases(
        db,
        user,
        product_module=product_module,
        case_manager_user_id=case_manager_user_id,
        active_only=True,
    )
    allowed_cases = [case for case in cases[:MAX_EXPORT_ROWS] if _case_allowed(db, user, case)]
    child_ids = {case.child_id for case in allowed_cases if case.child_id}
    parent_by_child = _parent_by_child(db, child_ids)
    parent_user_ids = {
        info["user_id"] for info in parent_by_child.values() if info.get("user_id")
    }
    last_login_by_user, has_portal_session, last_seen_by_user = _parent_portal_activity(
        db, parent_user_ids
    )

    rows: list[dict[str, Any]] = []
    for case in allowed_cases:
        parent = parent_by_child.get(case.child_id or -1, {})
        parent_user_id = parent.get("user_id")
        last_login = last_login_by_user.get(parent_user_id) if parent_user_id else None
        last_seen = last_seen_by_user.get(parent_user_id) if parent_user_id else None
        last_activity = _latest_activity_date(last_login, last_seen)
        days_since_activity = days_since(last_activity, as_of=today)
        cm = case_manager(db, case)
        rows.append(
            {
                "Case ID": export_case_id(case),
                "Client Name": case_service.case_child_display_name(case) or "",
                "Parent Name": parent.get("parent_name", ""),
                "Login Status": "Ready" if parent.get("login_ready") else "Not ready",
                "Has Logged In": "Yes"
                if parent_user_id and parent_user_id in has_portal_session
                else "No",
                "Last Login": last_login.date().isoformat() if last_login else "",
                "Last Seen": last_seen.date().isoformat() if last_seen else "",
                "Days Since Last Activity": days_since_activity
                if days_since_activity is not None
                else "",
                "Case Manager": user_display_name(cm),
            }
        )
    rows.sort(
        key=lambda r: (
            r["Days Since Last Activity"]
            if isinstance(r["Days Since Last Activity"], int)
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
    case_manager_user_id: int | None = None,
) -> list[dict[str, Any]]:
    """Therapists with active cases and completed sessions missing logs (2+ days old)."""
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

    assignment_rows = db.execute(
        select(CaseAssignment.therapist_user_id, CaseAssignment.case_id).where(
            CaseAssignment.case_id.in_(case_ids),
            CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
        )
    ).all()

    therapist_cases: dict[int, list[Case]] = defaultdict(list)
    for therapist_id, case_id in assignment_rows:
        case = cases_by_id.get(case_id)
        if case:
            therapist_cases[int(therapist_id)].append(case)

    therapist_ids = list(therapist_cases.keys())
    if not therapist_ids:
        return []

    missing_rows = db.execute(
        select(
            TherapySession.therapist_user_id,
            TherapySession.scheduled_date,
            TherapySession.case_id,
        )
        .outerjoin(DailyLog, DailyLog.session_id == TherapySession.id)
        .where(
            TherapySession.therapist_user_id.in_(therapist_ids),
            TherapySession.case_id.in_(case_ids),
            TherapySession.status == SessionStatus.COMPLETED,
            DailyLog.id.is_(None),
            TherapySession.scheduled_date <= cutoff,
        )
        .order_by(TherapySession.therapist_user_id, TherapySession.scheduled_date)
    ).all()

    missing_by_therapist: dict[int, list[date]] = defaultdict(list)
    missing_case_ids: dict[int, set[int]] = defaultdict(set)
    for therapist_id, scheduled_date, missing_case_id in missing_rows:
        tid = int(therapist_id)
        missing_by_therapist[tid].append(scheduled_date)
        missing_case_ids[tid].add(int(missing_case_id))

    last_submitted = dict(
        db.execute(
            select(TherapySession.therapist_user_id, func.max(DailyLog.submitted_at))
            .join(DailyLog, DailyLog.session_id == TherapySession.id)
            .where(
                TherapySession.therapist_user_id.in_(therapist_ids),
                TherapySession.case_id.in_(case_ids),
                DailyLog.submitted_at.isnot(None),
            )
            .group_by(TherapySession.therapist_user_id)
        ).all()
    )

    out: list[dict[str, Any]] = []
    for therapist_id in sorted(therapist_cases.keys()):
        missing_dates = missing_by_therapist.get(therapist_id, [])
        if not missing_dates:
            continue

        therapist = db.get(User, therapist_id)
        active_cases = therapist_cases[therapist_id]
        case_ids_str = "; ".join(export_case_id(c) for c in active_cases if export_case_id(c))
        cm_names = sorted(
            {
                user_display_name(case_manager(db, c))
                for c in active_cases
                if case_manager(db, c)
            }
        )
        oldest = min(missing_dates)
        newest = max(missing_dates)
        last_at = last_submitted.get(therapist_id)

        out.append(
            {
                "Therapist ID": export_therapist_id(therapist),
                "Therapist Name": user_display_name(therapist),
                "Mentor": user_display_name(mentor_for_therapist(db, therapist_id)),
                "Case Manager": ", ".join(cm_names),
                "Active Cases": len(active_cases),
                "Case IDs": case_ids_str,
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


def _ledger_billable_by_case(db: Session, case_ids: list[int], ym: str) -> dict[int, int]:
    if not case_ids:
        return {}
    return dict(
        db.execute(
            select(BillingLedger.case_id, func.count())
            .where(
                BillingLedger.case_id.in_(case_ids),
                BillingLedger.ledger_month == ym,
                BillingLedger.billable_status.in_([BillableStatus.BILLABLE, BillableStatus.INVOICED]),
            )
            .group_by(BillingLedger.case_id)
        ).all()
    )


def _build_billable_metrics(
    db: Session,
    cases: list[Case],
    case_ids: list[int],
    ym: str,
    start: date,
    end: date,
    session_stats: dict[int, dict[str, int]],
    *,
    leave_cache: dict[int, dict[str, int]],
) -> dict[int, dict[str, Any]]:
    approved_sessions = _approved_sessions_by_case(db, case_ids, start, end)
    approved_child_absence = _approved_child_absence_billable_by_case(db, case_ids, start, end)
    ledger_billable = _ledger_billable_by_case(db, case_ids, ym)
    cases_by_id = {c.id: c for c in cases if c.id in case_ids}
    out: dict[int, dict[str, Any]] = {}

    for case_id in case_ids:
        case = cases_by_id.get(case_id)
        stats = session_stats.get(case_id, {})
        approved = int(approved_sessions.get(case_id, 0))
        child_absence = int(approved_child_absence.get(case_id, 0))
        scheduled = int(stats.get("scheduled", 0))

        if case and is_homecare_case(case):
            billable = approved + child_absence
        else:
            billable = int(ledger_billable.get(case_id, 0))

        monthly_fixed = ""
        per_session_rate = ""
        leave_deduction = ""
        if case and is_shadow_case(case):
            fixed_pay = float(case.therapist_fixed_pay_inr or 0)
            monthly_fixed = fixed_pay if fixed_pay else ""
            rate = shadow_per_session_day_rate(fixed_pay or None, scheduled)
            per_session_rate = rate if rate else ""
            assign = active_assignment(db, case_id)
            therapist = assignment_therapist(db, assign)
            unpaid_days = 0
            if therapist:
                if therapist.id not in leave_cache:
                    leave_cache[therapist.id] = leave_days_in_month(db, therapist.id, ym)
                unpaid_days = int(leave_cache[therapist.id].get("unpaid", 0))
            deduction = shadow_leave_deduction_estimate(fixed_pay or None, scheduled, unpaid_days)
            leave_deduction = deduction if deduction else ""

        out[case_id] = {
            "approved_sessions": approved,
            "approved_child_absence": child_absence,
            "billable_sessions": billable,
            "monthly_fixed_pay": monthly_fixed,
            "per_session_day_rate": per_session_rate,
            "leave_deduction_estimate": leave_deduction,
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
