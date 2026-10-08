from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime, time, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.billing_calc_errors import MissingPackageCountError
from app.core.billing_validation import case_billing_dict, resolve_therapist_pay
from app.core.permissions import get_active_assignment
from app.core.session_defaults import default_session_mode_for_case
from app.models.assignment import CaseAssignment, CaseAssignmentStatus
from app.models.case import BillingType, Case, CompensationMode
from app.models.daily_log import DailyLog, LogApprovalStatus
from app.models.invoice import Invoice, InvoiceStatus
from app.models.invoice_line import InvoiceCaseLine, InvoiceSessionLine, SessionLineSource, SessionLineType
from app.models.invoice_manual_line import InvoiceManualLine, ManualLineStatus
from app.models.leave import LeaveStatus, TherapistLeave
from app.models.session import Session as TherapySession
from app.models.session import SessionStatus
from app.models.user import User
from app.core.session_times import effective_session_datetimes
from app.services import finance_payout_preview_service as payout_cycle
from app.services import invoice_attendance_service as attendance
from app.services import payout_settlement_service
from app.services import therapist_invoice_labels as labels
from app.services.reports_export_helpers import cases_by_ids, parent_by_child, case_people_export_fields


def _normalize_next_month_plan(raw: Any) -> dict[str, Any]:
    """Next-month plan is a session count (legacy sessions[] maps to count)."""
    if not isinstance(raw, dict):
        return {"notes": "", "session_count": 0}
    notes = str(raw.get("notes") or "").strip()[:2000]
    count_raw = raw.get("session_count")
    if count_raw is None and isinstance(raw.get("sessions"), list):
        count_raw = len(raw.get("sessions") or [])
    try:
        session_count = max(0, min(int(count_raw or 0), 60))
    except (TypeError, ValueError):
        session_count = 0
    return {"notes": notes, "session_count": session_count}


def parse_month(month: str) -> tuple[int, int, str]:
    """Return (year, month_num, display label). Accepts YYYY-MM or 'Mon YYYY'."""
    month = month.strip()
    if len(month) == 7 and month[4] == "-":
        y, m = int(month[:4]), int(month[5:7])
        label = date(y, m, 1).strftime("%b %Y")
        return y, m, label
    try:
        dt = datetime.strptime(month, "%b %Y")
        return dt.year, dt.month, month
    except ValueError:
        dt = datetime.strptime(month, "%B %Y")
        return dt.year, dt.month, dt.strftime("%b %Y")


def month_date_range(year: int, month: int) -> tuple[date, date]:
    last = monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last)


def session_duration_minutes(session: TherapySession, log: DailyLog | None = None) -> int:
    start, end = effective_session_datetimes(session, log)
    if start and end:
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)
        delta = int((end - start).total_seconds() / 60)
        return max(delta, 30)
    if session.start_time and session.end_time:
        start = datetime.combine(date.today(), session.start_time)
        end = datetime.combine(date.today(), session.end_time)
        delta = int((end - start).total_seconds() / 60)
        return max(delta, 30)
    return 60


def _per_session_amount(case: Case, *, db: Session | None = None, as_of: date | None = None) -> float:
    if db is not None and as_of is not None:
        from app.services import billing_rate_history_service

        return billing_rate_history_service.resolve_therapist_pay_as_of(db, case, as_of)
    return resolve_therapist_pay(case)


def _package_per_session_rate(
    case: Case,
    use_therapist_fixed: bool = True,
    *,
    db: Session | None = None,
    as_of: date | None = None,
) -> float:
    _ = use_therapist_fixed
    pkg_count = int(case.package_session_count) if case.package_session_count else 0
    if pkg_count <= 0:
        raise MissingPackageCountError(case)
    base = _per_session_amount(case, db=db, as_of=as_of)
    return base / pkg_count


def compute_session_line_amount(
    case: Case,
    line_type: SessionLineType,
    *,
    db: Session | None = None,
    as_of: date | None = None,
) -> float:
    _ = line_type
    if case.billing_type == BillingType.PER_SESSION:
        return round(_per_session_amount(case, db=db, as_of=as_of), 2)
    return round(_package_per_session_rate(case, db=db, as_of=as_of), 2)


def compute_case_totals(
    case: Case,
    session_lines: list[dict],
    *,
    db: Session | None = None,
    as_of: date | None = None,
) -> tuple[int, int, float]:
    regular_lines = [
        line for line in session_lines if not (line.get("flags") or {}).get("transition_log")
    ]
    transition_total = sum(
        float(line["amount_inr"])
        for line in session_lines
        if line.get("included") and (line.get("flags") or {}).get("transition_log")
    )
    included = sum(1 for s in regular_lines if s.get("included") and s.get("line_type") == SessionLineType.INCLUDED.value)
    additional = sum(1 for s in regular_lines if s.get("included") and s.get("line_type") == SessionLineType.ADDITIONAL.value)
    approved = sum(1 for s in regular_lines if s.get("included"))

    if payout_cycle.uses_calendar_day_pay(case):
        # Calendar-day gross needs first/last log + unpaid leave from the cycle engine.
        return included, additional, round(transition_total, 2)

    if case.billing_type == BillingType.PACKAGE:
        pkg_count = int(case.package_session_count) if case.package_session_count else 0
        if pkg_count <= 0:
            raise MissingPackageCountError(case)

    subtotal = payout_cycle.predicted_subtotal_inr(
        case, approved_sessions=approved, db=db, as_of=as_of
    )
    return included, additional, round(subtotal + transition_total, 2)


def _transition_total_from_lines(session_lines: list[dict]) -> float:
    return round(
        sum(
            float(line["amount_inr"])
            for line in session_lines
            if line.get("included") and (line.get("flags") or {}).get("transition_log")
        ),
        2,
    )


def engine_case_gross(
    case: Case,
    session_lines: list[dict],
    *,
    segment: payout_cycle.CycleSegment | None,
    before_leave_deduction: bool = False,
    db: Session | None = None,
    as_of: date | None = None,
) -> tuple[int, int, float]:
    """Payout-report gross for one therapist × case. No TDS."""
    included, additional, line_total = compute_case_totals(case, session_lines, db=db, as_of=as_of)
    if payout_cycle.uses_calendar_day_pay(case):
        if segment is None:
            return included, additional, line_total
        if before_leave_deduction:
            gross = round(
                payout_cycle.predicted_subtotal_inr(
                    case,
                    approved_sessions=segment.approved_sessions,
                    calendar_days=segment.calendar_days,
                    unpaid_leaves=0,
                    db=db,
                    as_of=as_of,
                )
                + segment.transition_total,
                2,
            )
            return included, additional, gross
        return included, additional, segment.therapist_gross(case, db=db, as_of=as_of)
    trans = _transition_total_from_lines(session_lines)
    approved = sum(
        1
        for line in session_lines
        if line.get("included") and not (line.get("flags") or {}).get("transition_log")
    )
    subtotal = payout_cycle.predicted_subtotal_inr(
        case, approved_sessions=approved, db=db, as_of=as_of
    )
    return included, additional, round(subtotal + trans, 2)



def therapist_active_on_session_date(
    db: Session,
    *,
    case_id: int,
    therapist_user_id: int,
    on_date,
) -> tuple[bool, str | None]:
    """Date-active assignment attribution for payout. Returns (ok, exception_code)."""
    from app.models.assignment import CaseAssignment, CaseAssignmentStatus

    rows = db.scalars(
        select(CaseAssignment).where(
            CaseAssignment.case_id == case_id,
            CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
            CaseAssignment.start_date <= on_date,
        )
    ).all()
    covering = []
    for a in rows:
        if a.end_date is not None and a.end_date < on_date:
            continue
        covering.append(a)
    if not covering:
        # Legacy: no assignment history — fall back to session.therapist_user_id match only
        return True, None
    matches = [a for a in covering if a.therapist_user_id == therapist_user_id]
    if len(covering) > 1:
        therapists = {a.therapist_user_id for a in covering}
        if len(therapists) > 1:
            from app.services import therapist_transition_service as transition_svc

            if transition_svc.is_transition_assignment_overlap(db, case_id, covering):
                if matches:
                    return True, None
                return False, "ASSIGNMENT_GAP"
            return False, "ASSIGNMENT_OVERLAP"
    if not matches:
        return False, "ASSIGNMENT_GAP"
    return True, None


def fetch_billable_sessions(
    db: Session,
    therapist_user_id: int,
    year: int,
    month: int,
) -> list[tuple[TherapySession, DailyLog, Case]]:
    start, end = month_date_range(year, month)
    stmt = (
        select(TherapySession)
        .join(DailyLog, DailyLog.session_id == TherapySession.id)
        .where(
            TherapySession.therapist_user_id == therapist_user_id,
            TherapySession.status == SessionStatus.COMPLETED,
            TherapySession.scheduled_date >= start,
            TherapySession.scheduled_date <= end,
            DailyLog.approval_status == LogApprovalStatus.APPROVED,
        )
        .options(selectinload(TherapySession.case).selectinload(Case.child))
        .order_by(TherapySession.scheduled_date, TherapySession.start_time)
    )
    sessions = db.scalars(stmt).all()
    result = []
    for s in sessions:
        log = s.daily_log
        if not (log and s.case and s.case.billing_type):
            continue
        ok, code = (True, None)
        if not log.transition_id:
            ok, code = therapist_active_on_session_date(
                db,
                case_id=s.case_id,
                therapist_user_id=therapist_user_id,
                on_date=s.scheduled_date,
            )
        if not ok:
            # Persist exception when ledger writes are on; never silently include mis-attributed pay.
            try:
                from app.services import billing_step6_service as step6

                step6.persist_calc_exceptions(
                    db,
                    case_id=s.case_id,
                    billing_month=s.scheduled_date.strftime("%Y-%m"),
                    exceptions=[
                        {
                            "code": code,
                            "message": f"Payout attribution {code} for session {s.id}",
                            "session_id": s.id,
                        }
                    ],
                )
            except Exception:
                pass
            continue
        result.append((s, log, s.case))
    return result


def _line_type_for_index(case: Case, index: int) -> SessionLineType:
    if case.billing_type == BillingType.PER_SESSION:
        return SessionLineType.PER_SESSION
    pkg_count = int(case.package_session_count or 0)
    return SessionLineType.INCLUDED if index < pkg_count else SessionLineType.ADDITIONAL


def session_line_dict(
    session: TherapySession,
    log: DailyLog,
    case: Case,
    line_type: SessionLineType,
    *,
    included: bool = True,
    source: SessionLineSource = SessionLineSource.LOG,
    extra_flags: dict | None = None,
    db: Session | None = None,
) -> dict:
    flags = dict(extra_flags or {})
    if log.transition_day_id and log.transition_day:
        amount = round(float(log.transition_day.pay_rate_inr), 2)
        flags.update(
            {
                "transition_log": True,
                "transition_id": log.transition_id,
                "transition_day_id": log.transition_day_id,
                "transition_day_type": log.transition_day.day_type,
            }
        )
    else:
        amount = compute_session_line_amount(
            case, line_type, db=db, as_of=session.scheduled_date
        )
    return {
        "session_id": session.id,
        "daily_log_id": log.id,
        "session_date": session.scheduled_date.isoformat(),
        "duration_minutes": session_duration_minutes(session, log),
        "line_type": line_type.value,
        "amount_inr": amount,
        "source": source.value,
        "included": included,
        "approval_status": (
            log.approval_status.value
            if hasattr(log.approval_status, "value")
            else str(log.approval_status)
        ),
        "flags": flags,
    }


def build_case_session_lines(case: Case, items: list[tuple[TherapySession, DailyLog]]) -> list[dict]:
    lines: list[dict] = []
    ordered = sorted(items, key=lambda x: (x[0].scheduled_date, x[0].start_time or time.min))
    regular_items = [(session, log) for session, log in ordered if not log.transition_id]
    transition_items = [(session, log) for session, log in ordered if log.transition_id]
    for idx, (session, log) in enumerate(regular_items):
        line_type = _line_type_for_index(case, idx)
        lines.append(session_line_dict(session, log, case, line_type))
    for session, log in transition_items:
        lines.append(session_line_dict(session, log, case, SessionLineType.PER_SESSION))
    return lines


def fetch_pending_late_sessions(
    db: Session,
    therapist_user_id: int,
    year: int,
    month: int,
) -> list[tuple[TherapySession, DailyLog, Case]]:
    start, end = month_date_range(year, month)
    stmt = (
        select(TherapySession)
        .join(DailyLog, DailyLog.session_id == TherapySession.id)
        .where(
            TherapySession.therapist_user_id == therapist_user_id,
            TherapySession.status == SessionStatus.COMPLETED,
            TherapySession.scheduled_date >= start,
            TherapySession.scheduled_date <= end,
            DailyLog.late_addition.is_(True),
            DailyLog.approval_status == LogApprovalStatus.PENDING,
        )
        .options(selectinload(TherapySession.case).selectinload(Case.child))
        .order_by(TherapySession.scheduled_date, TherapySession.start_time)
    )
    result = []
    for s in db.scalars(stmt).all():
        if s.daily_log and s.case and s.case.billing_type:
            result.append((s, s.daily_log, s.case))
    return result


def _all_case_sessions_in_month(
    db: Session,
    case_id: int,
    therapist_user_id: int,
    year: int,
    month: int,
) -> list[tuple[TherapySession, DailyLog]]:
    start, end = month_date_range(year, month)
    stmt = (
        select(TherapySession)
        .join(DailyLog, DailyLog.session_id == TherapySession.id)
        .where(
            TherapySession.case_id == case_id,
            TherapySession.therapist_user_id == therapist_user_id,
            TherapySession.status == SessionStatus.COMPLETED,
            TherapySession.scheduled_date >= start,
            TherapySession.scheduled_date <= end,
        )
        .order_by(TherapySession.scheduled_date, TherapySession.start_time)
    )
    rows = []
    for s in db.scalars(stmt).all():
        if s.daily_log:
            rows.append((s, s.daily_log))
    return rows


def _times_overlap(start_a: time, end_a: time, start_b: time, end_b: time) -> bool:
    return start_a < end_b and start_b < end_a


def create_late_session(
    db: Session,
    therapist_user_id: int,
    *,
    case_id: int,
    month: str,
    session_date: date,
    start_time: time,
    end_time: time,
    attendance_status: str,
    activities_done: str | None,
    observations: str | None,
    late_reason: str,
) -> dict[str, Any]:
    year, month_num, _ = parse_month(month)
    start, end = month_date_range(year, month_num)
    if session_date < start or session_date > end:
        raise ValueError("Session date must fall within the invoice month")

    if end_time <= start_time:
        raise ValueError("End time must be after start time")

    from datetime import datetime, timezone

    from app.services import session_service

    start_dt = datetime.combine(session_date, start_time, tzinfo=timezone.utc)
    end_dt = datetime.combine(session_date, end_time, tzinfo=timezone.utc)
    session_service.validate_manual_duration(start_dt, end_dt)

    case = db.scalars(select(Case).where(Case.id == case_id).options(selectinload(Case.child))).first()
    if not case:
        raise ValueError("Case not found")
    if not case.billing_type:
        raise ValueError("Case billing is not configured")

    if not get_active_assignment(db, case_id, therapist_user_id):
        raise ValueError("You are not actively assigned to this case")

    existing_same_day = db.scalars(
        select(TherapySession).where(
            TherapySession.case_id == case_id,
            TherapySession.therapist_user_id == therapist_user_id,
            TherapySession.scheduled_date == session_date,
            TherapySession.status.notin_((SessionStatus.CANCELLED, SessionStatus.RESCHEDULED)),
        )
    ).all()
    for existing in existing_same_day:
        if not existing.start_time or not existing.end_time:
            continue
        if not _times_overlap(start_time, end_time, existing.start_time, existing.end_time):
            continue
        if existing.status == SessionStatus.IN_PROGRESS:
            raise ValueError(
                "A session is already in progress for this case. End that session before adding another."
            )
        raise ValueError(
            "A session already exists at this date and time for this case. "
            "Edit the time or cancel the existing session first."
        )

    session = TherapySession(
        case_id=case_id,
        therapist_user_id=therapist_user_id,
        scheduled_date=session_date,
        start_time=start_time,
        end_time=end_time,
        mode=default_session_mode_for_case(case),
        status=SessionStatus.COMPLETED,
    )
    db.add(session)
    db.flush()

    log = DailyLog(
        session_id=session.id,
        attendance_status=attendance_status,
        activities_done=activities_done,
        observations=observations,
        submitted_at=datetime.now(timezone.utc),
        approval_status=LogApprovalStatus.PENDING,
        late_addition=True,
        late_reason=late_reason,
    )
    db.add(log)
    db.flush()

    all_in_month = _all_case_sessions_in_month(db, case_id, therapist_user_id, year, month_num)
    idx = next(i for i, (s, _) in enumerate(all_in_month) if s.id == session.id)
    line_type = _line_type_for_index(case, idx)
    line = session_line_dict(
        session,
        log,
        case,
        line_type,
        included=False,
        source=SessionLineSource.MANUAL_LATE,
        extra_flags={
            "added_late": True,
            "pending_approval": True,
            "pending_reason": "Added from invoice",
        },
    )
    return {
        "session_id": session.id,
        "daily_log_id": log.id,
        "case_id": case_id,
        "preview_line": line,
    }


def delete_late_session(db: Session, therapist_user_id: int, session_id: int) -> None:
    session = db.get(TherapySession, session_id)
    if not session or session.therapist_user_id != therapist_user_id:
        raise ValueError("Session not found")
    log = session.daily_log
    if not log or not log.late_addition:
        raise ValueError("Only late-added sessions can be removed this way")
    if log.approval_status != LogApprovalStatus.PENDING:
        raise ValueError("Cannot remove a late session after it has been reviewed")
    db.delete(log)
    db.delete(session)
    db.flush()


def _count_display_included(case: Case, session_lines: list[dict]) -> int:
    if case.billing_type == BillingType.PER_SESSION:
        return sum(1 for s in session_lines if s.get("included"))
    return sum(1 for s in session_lines if s.get("included") and s.get("line_type") == SessionLineType.INCLUDED.value)


def _assigned_billing_cases(db: Session, therapist_user_id: int) -> list[Case]:
    stmt = (
        select(Case)
        .join(CaseAssignment, CaseAssignment.case_id == Case.id)
        .where(
            CaseAssignment.therapist_user_id == therapist_user_id,
            CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
            Case.billing_type.isnot(None),
        )
        .options(selectinload(Case.child))
    )
    return list(db.scalars(stmt).unique().all())


def build_month_preview(db: Session, therapist_user_id: int, month: str) -> dict[str, Any]:
    year, month_num, label = parse_month(month)
    ym = f"{year}-{month_num:02d}"
    facts = attendance.month_attendance_facts(db, therapist_user_id=therapist_user_id, ym=ym)
    facts_by_case = {c["case_id"]: c for c in facts["cases"]}

    by_case: dict[int, dict] = {}
    for case in _assigned_billing_cases(db, therapist_user_id):
        by_case[case.id] = {"case": case, **facts_by_case.get(case.id, {})}

    for fact in facts["cases"]:
        if fact["case_id"] not in by_case:
            case = db.scalars(
                select(Case).where(Case.id == fact["case_id"]).options(selectinload(Case.child))
            ).first()
            if case:
                by_case[case.id] = {"case": case, **fact}

    case_groups: list[dict] = []
    subtotal = 0.0
    total_sessions = 0
    pending_approval_inr = 0.0
    pending_approval_count = 0

    for case_id, bucket in by_case.items():
        case = bucket["case"]
        session_lines = bucket.get("session_lines") or []
        child_absence_lines = bucket.get("child_absence_lines") or []
        leave_lines = bucket.get("leave_lines") or []
        pending_approval_lines = bucket.get("pending_approval_lines") or []
        case_attendance = bucket.get("attendance") or attendance._empty_attendance()
        has_activity = bucket.get("has_activity", False)
        billing_profile = bucket.get("billing_profile") or attendance.billing_profile_for_case(case).value

        absence_total = round(
            sum(float(l["amount_inr"]) for l in child_absence_lines if l.get("included")), 2
        )
        pending_case_inr = round(sum(float(p["amount_inr"]) for p in pending_approval_lines), 2)
        pending_approval_inr += pending_case_inr
        pending_approval_count += len(pending_approval_lines)

        segment = payout_cycle.segment_for_therapist(db, case, therapist_user_id, ym)
        _ms, month_end = month_date_range(year, month_num)
        included, additional, case_total = engine_case_gross(
            case,
            session_lines,
            segment=segment,
            before_leave_deduction=True,
            db=db,
            as_of=month_end,
        )
        case_total = round(case_total + absence_total, 2)
        subtotal += case_total
        total_sessions += len([s for s in session_lines if s.get("included")])

        case_groups.append({
            "case_id": case.id,
            "case_code": case.case_code,
            "child_name": case.child.full_name if case.child else None,
            "billing": case_billing_dict(case),
            "billing_profile": billing_profile,
            "product_module": (case.product_module or "").strip().lower(),
            "has_activity": has_activity,
            "attendance": case_attendance,
            "included_sessions": included,
            "additional_sessions": additional,
            "display_included_sessions": _count_display_included(case, session_lines),
            "therapist_share_inr": case_total,
            "pending_approval_inr": pending_case_inr,
            "pending_late_inr": pending_case_inr,
            "session_lines": session_lines,
            "child_absence_lines": child_absence_lines,
            "leave_day_lines": bucket.get("leave_day_lines") or [],
            "leave_lines": leave_lines,
            "pending_approval_lines": pending_approval_lines,
            "pending_late_lines": pending_approval_lines,
            "next_month_session_plan": {"notes": "", "session_count": 0},
            "cycle": {
                "calendarDays": segment.calendar_days if segment else 0,
                "unpaidLeaves": segment.unpaid_leaves if segment else 0,
                "transitionTotal": segment.transition_total if segment else 0,
                "approvedSessions": segment.approved_sessions if segment else 0,
            },
        })

    leave_balance = None
    therapist_user = db.get(User, therapist_user_id)
    if therapist_user:
        from app.services import leave_policy_service as policy

        leave_balance = policy.get_leave_balance(db, therapist_user, year=year)

    leave_deduction_inr = float(facts.get("leave_deduction_inr") or 0)
    net = round(max(subtotal - leave_deduction_inr, 0), 2)

    return {
        "month": ym,
        "month_label": label,
        "therapist_user_id": therapist_user_id,
        "total_sessions": total_sessions,
        "subtotal_inr": round(subtotal, 2),
        "pending_approval_inr": round(pending_approval_inr, 2),
        "pending_approval_count": pending_approval_count,
        "pending_late_inr": round(pending_approval_inr, 2),
        "pending_late_count": pending_approval_count,
        "leave_deduction_inr": leave_deduction_inr,
        "leave_details": [
            {**line, "case_id": group["case_id"], "case_code": group["case_code"]}
            for group in case_groups
            for line in (group.get("leave_day_lines") or [])
        ],
        "leave_balance": leave_balance,
        "attendance_summary": facts.get("attendance_summary") or {},
        "rejected_notes": facts.get("rejected_notes") or [],
        "net_amount_inr": net,
        "cases": case_groups,
    }


def apply_preview_edits(preview: dict, edits: dict) -> dict:
    """Apply therapist edits: exclude approved sessions only. Leave deduction stays static."""
    excluded_ids = set(edits.get("exclude_session_ids") or [])
    static_leave_deduction = float(preview.get("leave_deduction_inr") or 0)
    next_month_plans = edits.get("next_month_plans") or {}

    for case_group in preview["cases"]:
        case_id = case_group.get("case_id")
        if case_id is not None and str(case_id) in next_month_plans:
            case_group["next_month_session_plan"] = _normalize_next_month_plan(next_month_plans[str(case_id)])
        elif case_id is not None and case_id in next_month_plans:
            case_group["next_month_session_plan"] = _normalize_next_month_plan(next_month_plans[case_id])
        for line in case_group.get("session_lines", []):
            sid = line.get("session_id")
            if sid and sid in excluded_ids:
                line["included"] = False
                line["flags"] = {**(line.get("flags") or {}), "excluded_by_therapist": True}

    # If preview lacks case billing fields (plan-only patch), skip money recompute.
    if not any((c.get("billing") or c.get("billing_snapshot")) for c in preview.get("cases") or []):
        return preview

    subtotal = 0.0
    total_sessions = 0
    pending_approval_inr = 0.0
    pending_approval_count = 0
    for case_group in preview["cases"]:
        if not (case_group.get("billing") or case_group.get("billing_snapshot")):
            continue
        case = db_case_from_preview(case_group)
        cycle = case_group.get("cycle") or {}
        segment = None
        if payout_cycle.uses_calendar_day_pay(case):
            segment = payout_cycle.CycleSegment(
                therapist_user_id=int(preview.get("therapist_user_id") or 0),
                approved_sessions=int(cycle.get("approvedSessions") or 0),
                approved_absence=0,
                hours=0.0,
                calendar_days=int(cycle.get("calendarDays") or 0),
                unpaid_leaves=int(cycle.get("unpaidLeaves") or 0),
                paid_leaves=0,
                leave_credits=0,
                transition_days=0,
                transition_day_type="",
                transition_total=float(cycle.get("transitionTotal") or 0),
                therapist_start_date=None,
                case_start_date=None,
                case_end_date=None,
                first_log=None,
                last_log=None,
                is_incoming_replacement=False,
                is_outgoing_replacement=False,
            )
        included, additional, case_total = engine_case_gross(
            case, case_group.get("session_lines", []), segment=segment, before_leave_deduction=True
        )
        absence_total = round(
            sum(
                float(l["amount_inr"])
                for l in case_group.get("child_absence_lines", [])
                if l.get("included")
            ),
            2,
        )
        case_total = round(case_total + absence_total, 2)
        case_group["included_sessions"] = included
        case_group["additional_sessions"] = additional
        case_group["display_included_sessions"] = _count_display_included(case, case_group.get("session_lines", []))
        case_group["therapist_share_inr"] = case_total
        subtotal += case_total
        total_sessions += len([s for s in case_group.get("session_lines", []) if s.get("included")])
        plines = case_group.get("pending_approval_lines") or case_group.get("pending_late_lines") or []
        pending_case_inr = round(sum(float(p["amount_inr"]) for p in plines), 2)
        case_group["pending_approval_inr"] = pending_case_inr
        case_group["pending_late_inr"] = pending_case_inr
        pending_approval_inr += pending_case_inr
        pending_approval_count += len(plines)

    preview["subtotal_inr"] = round(subtotal, 2)
    preview["total_sessions"] = total_sessions
    preview["pending_approval_inr"] = round(pending_approval_inr, 2)
    preview["pending_approval_count"] = pending_approval_count
    preview["pending_late_inr"] = round(pending_approval_inr, 2)
    preview["pending_late_count"] = pending_approval_count
    preview["leave_deduction_inr"] = static_leave_deduction
    preview["net_amount_inr"] = round(max(subtotal - static_leave_deduction, 0), 2)
    return preview


def db_case_from_preview(case_group: dict) -> Case:
    """Minimal Case-like object for recomputation from preview billing dict."""
    b = case_group.get("billing") or case_group.get("billing_snapshot") or {}
    case = Case(
        id=case_group["case_id"],
        case_code=case_group.get("case_code") or "",
        child_id=0,
        service_type=b.get("service_type") or "",
        product_module=b.get("product_module") or "",
    )
    if b.get("billing_type"):
        case.billing_type = BillingType(b["billing_type"])
    if b.get("compensation_mode"):
        case.compensation_mode = CompensationMode(b["compensation_mode"])
    case.client_rate_per_session_inr = b.get("client_rate_per_session_inr")
    case.package_session_count = b.get("package_session_count")
    case.package_amount_inr = b.get("package_amount_inr")
    case.pay_share_amount_inr = b.get("pay_share_amount_inr")
    case.therapist_fixed_pay_inr = b.get("therapist_fixed_pay_inr")
    case.client_monthly_rate_inr = b.get("client_monthly_rate_inr")
    return case


_AMENDABLE_INVOICE_STATUSES = frozenset(
    {
        InvoiceStatus.DRAFT,
        InvoiceStatus.IN_REVIEW,
        InvoiceStatus.QUERIED,
        InvoiceStatus.REJECTED,
    }
)


def preview_has_billable_payout(preview: dict) -> bool:
    """True when the month has a non-zero therapist payout (sessions or calendar-day pay)."""
    if float(preview.get("net_amount_inr") or 0) > 0:
        return True
    if float(preview.get("subtotal_inr") or 0) > 0:
        return True
    return any(float(c.get("therapist_share_inr") or 0) > 0 for c in preview.get("cases") or [])


def submit_invoice_from_preview(
    db: Session,
    therapist_user_id: int,
    preview: dict,
    notes: str | None = None,
) -> Invoice:
    existing = db.scalars(
        select(Invoice).where(
            Invoice.therapist_user_id == therapist_user_id,
            Invoice.month == preview["month_label"],
            Invoice.status.in_([InvoiceStatus.DRAFT, InvoiceStatus.IN_REVIEW]),
        )
    ).first()
    if existing:
        raise ValueError("Invoice already submitted for this month")

    if not preview_has_billable_payout(preview):
        raise ValueError(
            "No billable payout for this month yet — add approved session logs or check your case billing setup."
        )

    pending_count = int(preview.get("pending_approval_count") or preview.get("pending_late_count") or 0)
    pending_inr = float(preview.get("pending_approval_inr") or preview.get("pending_late_inr") or 0)
    note_parts = []
    if notes:
        note_parts.append(notes.strip())
    if pending_count:
        note_parts.append(
            f"Contains {pending_count} session(s) pending approval "
            f"(₹{pending_inr:,.0f} excluded from payout)."
        )
    combined_notes = "\n".join(note_parts) if note_parts else None

    invoice = Invoice(
        therapist_user_id=therapist_user_id,
        month=preview["month_label"],
        amount_inr=preview["net_amount_inr"],
        subtotal_inr=preview["subtotal_inr"],
        leave_deduction_inr=preview["leave_deduction_inr"],
        adjustment_inr=0,
        sessions_count=preview["total_sessions"],
        status=InvoiceStatus.IN_REVIEW,
        notes=combined_notes,
    )
    db.add(invoice)
    db.flush()

    _replace_invoice_lines_from_preview(db, invoice, preview)
    invoice.status = InvoiceStatus.IN_REVIEW
    invoice.notes = combined_notes
    _prefill_tds_and_snapshot_settlement(db, invoice, preview)
    return invoice


def _prefill_tds_and_snapshot_settlement(db: Session, invoice: Invoice, preview: dict) -> None:
    """Prefill TDS from profile rate and freeze net_payable from settlement ladder."""
    try:
        rate = payout_settlement_service.resolve_tds_rate_percent(
            db, therapist_user_id=invoice.therapist_user_id
        )
        if preview.get("subtotal_inr") is not None:
            gross = float(preview["subtotal_inr"])
            leave = float(preview.get("leave_deduction_inr") or 0)
            taxable = max(gross - leave, 0.0)
        else:
            # net_amount_inr is already leave-adjusted — do not subtract leave again
            taxable = max(float(preview.get("net_amount_inr") or 0), 0.0)
        invoice.tds_inr = round(taxable * rate / 100.0, 2)
    except Exception:
        invoice.tds_inr = None
    if invoice.tds_inr is not None:
        settlement = payout_settlement_service.compute_invoice_settlement(db, invoice)
        payout_settlement_service.snapshot_settlement_on_invoice(db, invoice, settlement)


def _replace_invoice_lines_from_preview(db: Session, invoice: Invoice, preview: dict) -> None:
    for cl in list(invoice.case_lines):
        db.delete(cl)
    db.flush()

    invoice.amount_inr = preview["net_amount_inr"]
    invoice.subtotal_inr = preview["subtotal_inr"]
    invoice.leave_deduction_inr = preview["leave_deduction_inr"]
    invoice.sessions_count = preview["total_sessions"]

    for case_group in preview["cases"]:
        snapshot = dict(case_group.get("billing") or {})
        plan = case_group.get("next_month_session_plan")
        if plan:
            snapshot["next_month_session_plan"] = _normalize_next_month_plan(plan)
        # Freeze leave / absence display with the submitted totals (avoid live drift).
        snapshot["leave_lines"] = list(case_group.get("leave_lines") or [])
        snapshot["leave_day_lines"] = list(case_group.get("leave_day_lines") or [])
        snapshot["child_absence_lines"] = list(case_group.get("child_absence_lines") or [])
        case_line = InvoiceCaseLine(
            invoice_id=invoice.id,
            case_id=case_group["case_id"],
            case_code=case_group["case_code"],
            billing_type=case_group["billing"].get("billing_type", "PER_SESSION"),
            included_sessions=case_group["included_sessions"],
            additional_sessions=case_group["additional_sessions"],
            therapist_share_inr=case_group["therapist_share_inr"],
            billing_snapshot=snapshot,
        )
        db.add(case_line)
        db.flush()

        for sl in case_group.get("session_lines", []):
            if not sl.get("included"):
                continue
            flags = dict(sl.get("flags") or {})
            if sl.get("ui_label"):
                flags["ui_label"] = sl["ui_label"]
            if sl.get("breakdown_bucket"):
                flags["breakdown_bucket"] = sl["breakdown_bucket"]
            if sl.get("line_kind"):
                flags["line_kind"] = sl["line_kind"]
            db.add(
                InvoiceSessionLine(
                    invoice_case_line_id=case_line.id,
                    session_id=sl.get("session_id"),
                    daily_log_id=sl.get("daily_log_id"),
                    session_date=date.fromisoformat(sl["session_date"]),
                    duration_minutes=sl.get("duration_minutes", 60),
                    line_type=SessionLineType(sl["line_type"]),
                    amount_inr=sl["amount_inr"],
                    source=SessionLineSource(sl.get("source", SessionLineSource.LOG.value)),
                    included=True,
                    flags=flags,
                )
            )

        for sl in case_group.get("pending_approval_lines") or case_group.get("pending_late_lines") or []:
            flags = dict(sl.get("flags") or {})
            flags["provisional_amount_inr"] = sl["amount_inr"]
            if sl.get("ui_label"):
                flags["ui_label"] = sl["ui_label"]
            if sl.get("breakdown_bucket"):
                flags["breakdown_bucket"] = sl["breakdown_bucket"]
            if sl.get("line_kind"):
                flags["line_kind"] = sl["line_kind"]
            db.add(
                InvoiceSessionLine(
                    invoice_case_line_id=case_line.id,
                    session_id=sl.get("session_id"),
                    daily_log_id=sl.get("daily_log_id"),
                    session_date=date.fromisoformat(sl["session_date"]),
                    duration_minutes=sl.get("duration_minutes", 60),
                    line_type=SessionLineType(sl["line_type"]),
                    amount_inr=0,
                    source=SessionLineSource(sl.get("source", SessionLineSource.MANUAL_LATE.value)),
                    included=False,
                    flags=flags,
                )
            )
    db.flush()


def amend_invoice_from_preview(
    db: Session,
    invoice_id: int,
    therapist_user_id: int,
    preview: dict,
    notes: str | None = None,
) -> Invoice:
    invoice = db.scalars(
        select(Invoice)
        .where(Invoice.id == invoice_id)
        .options(selectinload(Invoice.case_lines))
    ).first()
    if not invoice:
        raise ValueError("Invoice not found")
    if invoice.therapist_user_id != therapist_user_id:
        raise ValueError("Not your invoice")
    if invoice.status not in (InvoiceStatus.IN_REVIEW, InvoiceStatus.QUERIED, InvoiceStatus.REJECTED):
        raise ValueError("This invoice cannot be amended")

    pending_count = int(preview.get("pending_approval_count") or preview.get("pending_late_count") or 0)
    pending_inr = float(preview.get("pending_approval_inr") or preview.get("pending_late_inr") or 0)
    note_parts = []
    if notes:
        note_parts.append(notes.strip())
    if pending_count:
        note_parts.append(
            f"Contains {pending_count} session(s) pending approval "
            f"(₹{pending_inr:,.0f} excluded from payout)."
        )
    combined_notes = "\n".join(note_parts) if note_parts else invoice.notes

    _replace_invoice_lines_from_preview(db, invoice, preview)
    invoice.status = InvoiceStatus.IN_REVIEW
    invoice.notes = combined_notes
    _prefill_tds_and_snapshot_settlement(db, invoice, preview)
    return invoice


def _merge_case_with_attendance_facts(stored_case: dict, fact_case: dict | None) -> dict:
    """Overlay live attendance facts onto persisted invoice case rows.

    Leave / child-absence lines stay frozen from submit (billing_snapshot) so
    they cannot diverge from stored leave_deduction_inr / net totals. Pending
    approval lines remain live so therapists still see what needs review.
    """
    if not fact_case:
        return stored_case
    merged = dict(stored_case)
    for key in (
        "attendance",
        "has_activity",
        "billing_profile",
        "pending_approval_lines",
        "pending_approval_inr",
    ):
        if key in fact_case:
            merged[key] = fact_case[key]
    pending_lines = fact_case.get("pending_approval_lines") or merged.get("pending_late_lines") or []
    merged["pending_approval_lines"] = pending_lines
    merged["pending_late_lines"] = pending_lines
    pending_inr = fact_case.get("pending_approval_inr")
    if pending_inr is not None:
        merged["pending_approval_inr"] = pending_inr
        merged["pending_late_inr"] = pending_inr
    return merged


def _session_line_entry(sl: InvoiceSessionLine) -> tuple[dict, bool]:
    flags = sl.flags or {}
    provisional = flags.get("provisional_amount_inr")
    is_pending = provisional is not None and not sl.included
    entry = {
        "id": sl.id,
        "session_id": sl.session_id,
        "daily_log_id": sl.daily_log_id,
        "session_date": sl.session_date.isoformat(),
        "duration_minutes": sl.duration_minutes,
        "line_type": sl.line_type.value,
        "amount_inr": float(provisional if is_pending else sl.amount_inr),
        "display_amount_inr": float(provisional if is_pending else sl.amount_inr),
        "source": sl.source.value,
        "included": sl.included,
        "flags": flags,
        "line_kind": flags.get("line_kind") or ("PENDING_LOG" if is_pending else "SESSION"),
        "breakdown_bucket": flags.get("breakdown_bucket")
        or (
            labels.BUCKET_PENDING
            if is_pending
            else (labels.BUCKET_IN_PAY if sl.included else labels.BUCKET_INFO)
        ),
        "ui_label": flags.get("ui_label")
        or labels.session_completed_label(line_type=sl.line_type.value),
        "status_tag": labels.PENDING_TAG if is_pending else None,
    }
    return entry, is_pending


def _case_group_from_case_line(db: Session, cl: InvoiceCaseLine) -> tuple[dict, float, int]:
    session_lines: list[dict] = []
    pending_late_lines: list[dict] = []
    pending_late_inr = 0.0
    pending_late_count = 0
    for sl in cl.session_lines:
        entry, is_pending = _session_line_entry(sl)
        if is_pending:
            pending_late_lines.append(entry)
            pending_late_inr += float(entry["amount_inr"])
            pending_late_count += 1
        else:
            session_lines.append(entry)

    child_name = None
    case_row = db.get(Case, cl.case_id)
    if case_row and case_row.child:
        child_name = case_row.child.full_name
    snapshot = cl.billing_snapshot if isinstance(cl.billing_snapshot, dict) else {}
    plan = snapshot.get("next_month_session_plan") if isinstance(snapshot, dict) else None
    case_group = {
        "case_id": cl.case_id,
        "case_code": cl.case_code,
        "child_name": child_name,
        "billing_type": cl.billing_type,
        "included_sessions": cl.included_sessions,
        "additional_sessions": cl.additional_sessions,
        "therapist_share_inr": float(cl.therapist_share_inr),
        "billing_snapshot": cl.billing_snapshot,
        "billing": cl.billing_snapshot,
        "product_module": str(snapshot.get("product_module") or "").strip().lower(),
        "pending_approval_inr": round(pending_late_inr, 2),
        "pending_late_inr": round(pending_late_inr, 2),
        "session_lines": session_lines,
        "pending_approval_lines": pending_late_lines,
        "pending_late_lines": pending_late_lines,
        "leave_lines": list(snapshot.get("leave_lines") or []) if isinstance(snapshot, dict) else [],
        "leave_day_lines": list(snapshot.get("leave_day_lines") or []) if isinstance(snapshot, dict) else [],
        "child_absence_lines": list(snapshot.get("child_absence_lines") or [])
        if isinstance(snapshot, dict)
        else [],
        "next_month_session_plan": _normalize_next_month_plan(plan or {}),
    }
    return case_group, pending_late_inr, pending_late_count


def _stored_invoice_totals(invoice: Invoice) -> tuple[float, float, float]:
    subtotal = float(
        invoice.subtotal_inr if invoice.subtotal_inr is not None else invoice.amount_inr or 0
    )
    leave = float(invoice.leave_deduction_inr or 0)
    net = float(invoice.amount_inr or max(subtotal - leave, 0))
    return subtotal, leave, net


def _synthetic_case_groups_from_stored_header(
    db: Session, invoice: Invoice, subtotal_inr: float
) -> list[dict]:
    assigned = _assigned_billing_cases(db, invoice.therapist_user_id)
    if not assigned:
        return []
    if len(assigned) == 1:
        shares = [round(subtotal_inr, 2)]
    else:
        first = round(subtotal_inr * 0.4, 2)
        shares = [first, round(subtotal_inr - first, 2)]
    per_case_sessions = max(int(invoice.sessions_count or 0) // len(assigned), 0)
    groups: list[dict] = []
    for case, share in zip(assigned, shares):
        groups.append(
            {
                "case_id": case.id,
                "case_code": case.case_code,
                "child_name": case.child.full_name if case.child else None,
                "billing": case_billing_dict(case),
                "billing_snapshot": case_billing_dict(case),
                "included_sessions": per_case_sessions,
                "additional_sessions": 0,
                "therapist_share_inr": share,
                "session_lines": [],
                "child_absence_lines": [],
                "pending_approval_lines": [],
                "pending_late_lines": [],
                "pending_approval_inr": 0,
                "pending_late_inr": 0,
                "has_activity": share > 0,
                "snapshot_incomplete": True,
            }
        )
    return groups


def _breakdown_from_live_preview(db: Session, invoice: Invoice) -> dict:
    preview = build_month_preview(db, invoice.therapist_user_id, invoice.month)
    subtotal, leave_ded, net = _stored_invoice_totals(invoice)
    use_stored = invoice.subtotal_inr is not None or invoice.amount_inr is not None
    return {
        "id": invoice.id,
        "therapist_user_id": invoice.therapist_user_id,
        "month": invoice.month,
        "status": invoice.status.value,
        "subtotal_inr": subtotal if use_stored else float(preview["subtotal_inr"]),
        "leave_deduction_inr": leave_ded if use_stored else float(preview["leave_deduction_inr"]),
        "adjustment_inr": float(invoice.adjustment_inr or 0),
        "amount_inr": net if use_stored else float(preview["net_amount_inr"]),
        "net_amount_inr": net if use_stored else float(preview["net_amount_inr"]),
        "sessions_count": int(invoice.sessions_count or preview["total_sessions"]),
        "pending_approval_inr": preview.get("pending_approval_inr", preview.get("pending_late_inr", 0)),
        "pending_approval_count": preview.get("pending_approval_count", preview.get("pending_late_count", 0)),
        "pending_late_inr": preview.get("pending_late_inr", 0),
        "pending_late_count": preview.get("pending_late_count", 0),
        "notes": invoice.notes,
        "reviewer_comment": invoice.reviewer_comment,
        "cases": preview.get("cases") or [],
        "leave_details": preview.get("leave_details") or [],
        "leave_balance": preview.get("leave_balance"),
        "attendance_summary": preview.get("attendance_summary") or {},
        "rejected_notes": preview.get("rejected_notes") or [],
        "from_preview": True,
    }


def _breakdown_from_stored_header(db: Session, invoice: Invoice) -> dict:
    subtotal, leave_ded, net = _stored_invoice_totals(invoice)
    live_preview = build_month_preview(db, invoice.therapist_user_id, invoice.month)
    preview_cases = live_preview.get("cases") or []
    preview_subtotal = sum(float(c.get("therapist_share_inr") or 0) for c in preview_cases)
    if preview_subtotal > 0:
        ratio = subtotal / preview_subtotal if subtotal else 1.0
        cases = []
        for pc in preview_cases:
            cloned = dict(pc)
            cloned["therapist_share_inr"] = round(float(pc.get("therapist_share_inr") or 0) * ratio, 2)
            if not cloned.get("session_lines"):
                cloned["snapshot_incomplete"] = True
            cases.append(cloned)
    else:
        cases = _synthetic_case_groups_from_stored_header(db, invoice, subtotal)

    facts_by_case = {c["case_id"]: c for c in preview_cases}
    cases = [_merge_case_with_attendance_facts(c, facts_by_case.get(c["case_id"])) for c in cases]

    return {
        "id": invoice.id,
        "therapist_user_id": invoice.therapist_user_id,
        "month": invoice.month,
        "status": invoice.status.value,
        "subtotal_inr": subtotal,
        "leave_deduction_inr": leave_ded,
        "adjustment_inr": float(invoice.adjustment_inr or 0),
        "amount_inr": net,
        "net_amount_inr": net,
        "sessions_count": int(invoice.sessions_count or 0),
        "pending_approval_inr": 0,
        "pending_approval_count": 0,
        "pending_late_inr": 0,
        "pending_late_count": 0,
        "notes": invoice.notes,
        "reviewer_comment": invoice.reviewer_comment,
        "cases": cases,
        "manual_lines": [_manual_line_dict(ml) for ml in list(invoice.manual_lines or [])],
        "leave_details": [],
        "leave_balance": live_preview.get("leave_balance"),
        "attendance_summary": live_preview.get("attendance_summary") or {},
        "rejected_notes": live_preview.get("rejected_notes") or [],
        "from_stored_header": True,
        "snapshot_incomplete": not any((c.get("session_lines") or []) for c in cases),
    }


def _breakdown_from_persisted_case_lines(db: Session, invoice: Invoice) -> dict:
    cases = []
    pending_late_inr = 0.0
    pending_late_count = 0
    for cl in invoice.case_lines:
        case_group, case_pending_inr, case_pending_count = _case_group_from_case_line(db, cl)
        pending_late_inr += case_pending_inr
        pending_late_count += case_pending_count
        cases.append(case_group)

    live_preview = build_month_preview(db, invoice.therapist_user_id, invoice.month)
    facts_by_case = {c["case_id"]: c for c in live_preview.get("cases", [])}
    cases = [_merge_case_with_attendance_facts(c, facts_by_case.get(c["case_id"])) for c in cases]
    subtotal, leave_ded, net = _stored_invoice_totals(invoice)

    return {
        "id": invoice.id,
        "therapist_user_id": invoice.therapist_user_id,
        "month": invoice.month,
        "status": invoice.status.value,
        "subtotal_inr": subtotal,
        "leave_deduction_inr": leave_ded,
        "adjustment_inr": float(invoice.adjustment_inr or 0),
        "amount_inr": net,
        "net_amount_inr": net,
        "sessions_count": int(invoice.sessions_count or 0),
        "pending_approval_inr": live_preview.get("pending_approval_inr", round(pending_late_inr, 2)),
        "pending_approval_count": live_preview.get("pending_approval_count", pending_late_count),
        "pending_late_inr": round(pending_late_inr, 2),
        "pending_late_count": pending_late_count,
        "notes": invoice.notes,
        "reviewer_comment": invoice.reviewer_comment,
        "cases": cases,
        "manual_lines": [_manual_line_dict(ml) for ml in list(invoice.manual_lines or [])],
        "attendance_summary": live_preview.get("attendance_summary") or {},
        "rejected_notes": live_preview.get("rejected_notes") or [],
        "leave_balance": live_preview.get("leave_balance"),
        "snapshot_incomplete": not any((c.get("session_lines") or []) for c in cases),
    }


def _breakdown_from_persisted_lines(db: Session, invoice: Invoice) -> dict:
    cases = []
    pending_late_inr = 0.0
    pending_late_count = 0
    for cl in invoice.case_lines:
        case_group, case_pending_inr, case_pending_count = _case_group_from_case_line(db, cl)
        pending_late_inr += case_pending_inr
        pending_late_count += case_pending_count
        cases.append(case_group)

    live_preview = build_month_preview(db, invoice.therapist_user_id, invoice.month)
    facts_by_case = {c["case_id"]: c for c in live_preview.get("cases", [])}
    cases = [_merge_case_with_attendance_facts(c, facts_by_case.get(c["case_id"])) for c in cases]
    subtotal, leave_ded, net = _stored_invoice_totals(invoice)

    return {
        "id": invoice.id,
        "therapist_user_id": invoice.therapist_user_id,
        "month": invoice.month,
        "status": invoice.status.value,
        "subtotal_inr": subtotal,
        "leave_deduction_inr": leave_ded,
        "adjustment_inr": float(invoice.adjustment_inr or 0),
        "amount_inr": net,
        "net_amount_inr": net,
        "sessions_count": invoice.sessions_count,
        "pending_approval_inr": live_preview.get("pending_approval_inr", round(pending_late_inr, 2)),
        "pending_approval_count": live_preview.get("pending_approval_count", pending_late_count),
        "pending_late_inr": round(pending_late_inr, 2),
        "pending_late_count": pending_late_count,
        "notes": invoice.notes,
        "reviewer_comment": invoice.reviewer_comment,
        "cases": cases,
        "manual_lines": [_manual_line_dict(ml) for ml in list(invoice.manual_lines or [])],
        "attendance_summary": live_preview.get("attendance_summary") or {},
        "rejected_notes": live_preview.get("rejected_notes") or [],
        "leave_balance": live_preview.get("leave_balance"),
    }


def invoice_breakdown(db: Session, invoice_id: int) -> dict | None:
    invoice = db.scalars(
        select(Invoice)
        .where(Invoice.id == invoice_id)
        .options(
            selectinload(Invoice.case_lines).selectinload(InvoiceCaseLine.session_lines),
            selectinload(Invoice.manual_lines),
        )
    ).first()
    if not invoice:
        return None

    line_count = sum(len(cl.session_lines) for cl in invoice.case_lines)
    if line_count > 0:
        return _breakdown_from_persisted_lines(db, invoice)
    if invoice.case_lines:
        return _breakdown_from_persisted_case_lines(db, invoice)
    if invoice.status in _AMENDABLE_INVOICE_STATUSES:
        return _breakdown_from_live_preview(db, invoice)
    return _breakdown_from_stored_header(db, invoice)


def _manual_line_dict(line: InvoiceManualLine) -> dict:
    status = line.status.value if hasattr(line.status, "value") else str(line.status)
    return {
        "id": line.id,
        "invoice_id": line.invoice_id,
        "case_id": line.case_id,
        "description": line.description,
        "quantity": float(line.quantity),
        "amount_inr": float(line.amount_inr),
        "pay_share_inr": float(line.pay_share_inr),
        "status": status,
        "added_by_user_id": line.added_by_user_id,
        "approved_by_user_id": line.approved_by_user_id,
    }


def list_manual_lines(db: Session, invoice_id: int) -> list[dict]:
    invoice = db.get(Invoice, invoice_id)
    if not invoice:
        raise ValueError("Invoice not found")
    return [_manual_line_dict(ml) for ml in list(invoice.manual_lines or [])]


def create_manual_line(
    db: Session,
    invoice: Invoice,
    *,
    added_by_user_id: int,
    description: str,
    amount_inr: float,
    pay_share_inr: float,
    case_id: int | None = None,
    quantity: float = 1,
) -> InvoiceManualLine:
    if invoice.status not in (InvoiceStatus.DRAFT, InvoiceStatus.IN_REVIEW):
        raise ValueError("Manual lines can only be added to draft or in-review invoices")
    if case_id is not None:
        case = db.get(Case, case_id)
        if not case:
            raise ValueError("Case not found")
    line = InvoiceManualLine(
        invoice_id=invoice.id,
        case_id=case_id,
        description=description.strip(),
        quantity=quantity,
        amount_inr=amount_inr,
        pay_share_inr=pay_share_inr,
        status=ManualLineStatus.PENDING,
        added_by_user_id=added_by_user_id,
    )
    db.add(line)
    db.flush()
    return line


def recalculate_invoice_totals(db: Session, invoice: Invoice) -> None:
    """Recalculate invoice adjustment_inr from all currently approved manual lines."""
    invoice.adjustment_inr = approved_manual_lines_total(invoice)
    db.flush()


def review_manual_line(
    db: Session,
    line: InvoiceManualLine,
    *,
    approver_user_id: int,
    approve: bool,
) -> InvoiceManualLine:
    line.status = ManualLineStatus.APPROVED if approve else ManualLineStatus.REJECTED
    line.approved_by_user_id = approver_user_id
    db.flush()
    # Recalculate parent invoice totals after any line status change.
    invoice = db.get(Invoice, line.invoice_id)
    if invoice:
        recalculate_invoice_totals(db, invoice)
    return line


def approved_manual_lines_total(invoice: Invoice) -> float:
    total = 0.0
    for ml in invoice.manual_lines or []:
        if ml.status == ManualLineStatus.APPROVED:
            total += float(ml.pay_share_inr)
    return round(total, 2)


def export_invoice_csv(db: Session, invoice_id: int) -> str:
    import csv
    import io

    data = invoice_breakdown(db, invoice_id)
    if not data:
        raise ValueError("Invoice not found")
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "date",
            "case_code",
            "child_name",
            "parent_name",
            "duration_minutes",
            "line_type",
            "amount_inr",
            "included",
            "approval_status",
            "late_addition",
            "auto_ended",
            "source",
        ]
    )
    case_ids = {
        int(case_group["case_id"])
        for case_group in data.get("cases", [])
        if case_group.get("case_id")
    }
    cases_map = cases_by_ids(db, case_ids)
    parents = parent_by_child(
        db, {c.child_id for c in cases_map.values() if c.child_id}
    )
    for case_group in data.get("cases", []):
        child = case_group.get("child_name") or ""
        code = case_group.get("case_code") or ""
        case_row = cases_map.get(int(case_group["case_id"])) if case_group.get("case_id") else None
        parent_info = None
        if case_row and case_row.child_id:
            parent_info = parents.get(case_row.child_id)
        parent_name = case_people_export_fields(
            case_row, parent_info=parent_info, include_therapist=False
        )["Parent Name"]
        for sl in case_group.get("session_lines", []):
            flags = sl.get("flags") or {}
            writer.writerow(
                [
                    sl.get("session_date", ""),
                    code,
                    child,
                    parent_name,
                    sl.get("duration_minutes", ""),
                    sl.get("line_type", ""),
                    sl.get("amount_inr", ""),
                    sl.get("included", ""),
                    sl.get("approval_status", ""),
                    flags.get("added_late", False),
                    "",
                    sl.get("source", ""),
                ]
            )
        for sl in case_group.get("pending_late_lines", []):
            flags = sl.get("flags") or {}
            writer.writerow(
                [
                    sl.get("session_date", ""),
                    code,
                    child,
                    parent_name,
                    sl.get("duration_minutes", ""),
                    sl.get("line_type", ""),
                    sl.get("amount_inr", ""),
                    False,
                    sl.get("approval_status", "PENDING"),
                    True,
                    "",
                    "forgotten",
                ]
            )
    for ml in data.get("manual_lines", []):
        if ml.get("status") != "APPROVED":
            continue
        writer.writerow(
            [
                "",
                "",
                "",
                "",
                "",
                "MANUAL",
                ml.get("pay_share_inr", ""),
                True,
                ml.get("status", ""),
                False,
                "",
                ml.get("description", ""),
            ]
        )
    return output.getvalue()


def export_month_preview_csv(db: Session, therapist_user_id: int, month: str) -> str:
    import csv
    import io

    preview = build_month_preview(db, therapist_user_id, month)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "date",
            "case_code",
            "child_name",
            "duration_minutes",
            "line_type",
            "amount_inr",
            "included",
            "approval_status",
            "late_addition",
            "source",
        ]
    )
    for case_group in preview.get("cases", []):
        child = case_group.get("child_name") or ""
        code = case_group.get("case_code") or ""
        for sl in case_group.get("session_lines", []):
            flags = sl.get("flags") or {}
            writer.writerow(
                [
                    sl.get("session_date", ""),
                    code,
                    child,
                    sl.get("duration_minutes", ""),
                    sl.get("line_type", ""),
                    sl.get("amount_inr", ""),
                    sl.get("included", ""),
                    sl.get("approval_status", ""),
                    flags.get("added_late", False),
                    sl.get("source", ""),
                ]
            )
        for sl in case_group.get("pending_late_lines", []):
            writer.writerow(
                [
                    sl.get("session_date", ""),
                    code,
                    child,
                    sl.get("duration_minutes", ""),
                    sl.get("line_type", ""),
                    sl.get("amount_inr", ""),
                    False,
                    sl.get("approval_status", "PENDING"),
                    True,
                    "forgotten",
                ]
            )
    return output.getvalue()
