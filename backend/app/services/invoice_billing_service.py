from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime, time, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.billing_validation import case_billing_dict
from app.core.permissions import get_active_assignment
from app.models.assignment import CaseAssignment, CaseAssignmentStatus
from app.models.case import BillingType, Case, CompensationMode
from app.models.daily_log import DailyLog, LogApprovalStatus
from app.models.invoice import Invoice, InvoiceStatus
from app.models.invoice_line import InvoiceCaseLine, InvoiceSessionLine, SessionLineSource, SessionLineType
from app.models.leave import LeaveStatus, TherapistLeave
from app.models.session import Session as TherapySession
from app.models.session import SessionMode, SessionStatus
from app.models.user import User


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


def session_duration_minutes(session: TherapySession) -> int:
    if session.actual_start_at and session.actual_end_at:
        start = session.actual_start_at
        end = session.actual_end_at
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


def _per_session_amount(case: Case) -> float:
    rate = float(case.client_rate_per_session_inr or 0)
    pct = float(case.pay_share_pct or 0) / 100.0
    return rate * pct


def _package_per_session_rate(case: Case, use_therapist_fixed: bool) -> float:
    pkg_count = int(case.package_session_count or 1)
    if use_therapist_fixed:
        base = float(case.therapist_fixed_pay_inr or 0)
    else:
        base = float(case.package_amount_inr or 0) * (float(case.pay_share_pct or 0) / 100.0)
    return base / pkg_count


def compute_session_line_amount(case: Case, line_type: SessionLineType) -> float:
    if case.billing_type == BillingType.PER_SESSION:
        return round(_per_session_amount(case), 2)
    use_fixed = case.compensation_mode == CompensationMode.FIXED_LUMP
    return round(_package_per_session_rate(case, use_fixed), 2)


def compute_case_totals(case: Case, session_lines: list[dict]) -> tuple[int, int, float]:
    included = sum(1 for s in session_lines if s.get("included") and s.get("line_type") == SessionLineType.INCLUDED.value)
    additional = sum(1 for s in session_lines if s.get("included") and s.get("line_type") == SessionLineType.ADDITIONAL.value)
    per_session = sum(1 for s in session_lines if s.get("included") and s.get("line_type") == SessionLineType.PER_SESSION.value)

    if case.billing_type == BillingType.PER_SESSION:
        total = sum(s["amount_inr"] for s in session_lines if s.get("included"))
        return 0, 0, round(total, 2)

    pkg_count = int(case.package_session_count or 1)
    active_lines = [s for s in session_lines if s.get("included")]

    if case.compensation_mode == CompensationMode.FIXED_LUMP:
        fixed = float(case.therapist_fixed_pay_inr or 0)
        per_unit = fixed / pkg_count
        if included >= pkg_count:
            included_amt = fixed
        else:
            included_amt = included * per_unit
        additional_amt = additional * per_unit
        total = round(included_amt + additional_amt, 2)
        return included, additional, total

    pct = float(case.pay_share_pct or 0) / 100.0
    pkg_amt = float(case.package_amount_inr or 0)
    per_sess = (pkg_amt / pkg_count) * pct
    included_amt = included * per_sess
    additional_amt = additional * per_sess
    total = round(included_amt + additional_amt, 2)
    return included, additional, total


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
        if log and s.case and s.case.billing_type:
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
) -> dict:
    flags = dict(extra_flags or {})
    amount = compute_session_line_amount(case, line_type)
    return {
        "session_id": session.id,
        "daily_log_id": log.id,
        "session_date": session.scheduled_date.isoformat(),
        "duration_minutes": session_duration_minutes(session),
        "line_type": line_type.value,
        "amount_inr": amount,
        "source": source.value,
        "included": included,
        "approval_status": log.approval_status.value,
        "flags": flags,
    }


def build_case_session_lines(case: Case, items: list[tuple[TherapySession, DailyLog]]) -> list[dict]:
    lines: list[dict] = []
    for idx, (session, log) in enumerate(sorted(items, key=lambda x: (x[0].scheduled_date, x[0].start_time or time.min))):
        line_type = _line_type_for_index(case, idx)
        lines.append(session_line_dict(session, log, case, line_type))
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

    case = db.scalars(select(Case).where(Case.id == case_id).options(selectinload(Case.child))).first()
    if not case:
        raise ValueError("Case not found")
    if not case.billing_type:
        raise ValueError("Case billing is not configured")

    if not get_active_assignment(db, case_id, therapist_user_id):
        raise ValueError("You are not actively assigned to this case")

    for existing, log in _all_case_sessions_in_month(db, case_id, therapist_user_id, year, month_num):
        if existing.scheduled_date == session_date and existing.start_time and existing.end_time:
            if _times_overlap(start_time, end_time, existing.start_time, existing.end_time):
                raise ValueError("A session already exists at this date and time for this case")

    session = TherapySession(
        case_id=case_id,
        therapist_user_id=therapist_user_id,
        scheduled_date=session_date,
        start_time=start_time,
        end_time=end_time,
        mode=SessionMode.HOME,
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
        extra_flags={"added_late": True, "pending_approval": True},
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


def compute_leave_deduction(db: Session, therapist_user_id: int, year: int, month: int) -> tuple[float, list[dict]]:
    start, end = month_date_range(year, month)
    leaves = db.scalars(
        select(TherapistLeave).where(
            TherapistLeave.therapist_user_id == therapist_user_id,
            TherapistLeave.start_date <= end,
            TherapistLeave.end_date >= start,
        )
    ).all()
    daily_rate = 500.0
    deduction = 0.0
    details: list[dict] = []
    for leave in leaves:
        if leave.status == LeaveStatus.APPROVED:
            details.append({
                "leave_id": leave.id,
                "leave_type": leave.leave_type.value,
                "start_date": leave.start_date.isoformat(),
                "end_date": leave.end_date.isoformat(),
                "status": leave.status.value,
                "deduction_inr": 0,
                "note": "Approved leave — no deduction",
            })
            continue
        days = (min(leave.end_date, end) - max(leave.start_date, start)).days + 1
        amt = days * daily_rate
        deduction += amt
        details.append({
            "leave_id": leave.id,
            "leave_type": leave.leave_type.value,
            "start_date": leave.start_date.isoformat(),
            "end_date": leave.end_date.isoformat(),
            "status": leave.status.value,
            "deduction_inr": amt,
            "note": "Unapproved or pending leave deduction",
        })
    return round(deduction, 2), details


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
    billable = fetch_billable_sessions(db, therapist_user_id, year, month_num)
    pending_late = fetch_pending_late_sessions(db, therapist_user_id, year, month_num)

    by_case: dict[int, dict] = {}

    def ensure_case(case: Case) -> dict:
        if case.id not in by_case:
            by_case[case.id] = {
                "case": case,
                "approved": [],
                "pending": [],
            }
        return by_case[case.id]

    for case in _assigned_billing_cases(db, therapist_user_id):
        ensure_case(case)

    for session, log, case in billable:
        ensure_case(case)["approved"].append((session, log))

    for session, log, case in pending_late:
        ensure_case(case)["pending"].append((session, log))

    case_groups: list[dict] = []
    subtotal = 0.0
    total_sessions = 0
    pending_late_inr = 0.0
    pending_late_count = 0

    for case_id, bucket in by_case.items():
        case = bucket["case"]
        approved_items = bucket["approved"]
        pending_items = bucket["pending"]

        session_lines = build_case_session_lines(case, approved_items) if approved_items else []

        pending_lines: list[dict] = []
        if pending_items:
            all_for_index = sorted(
                approved_items + pending_items,
                key=lambda x: (x[0].scheduled_date, x[0].start_time or time.min),
            )
            index_by_session = {s.id: i for i, (s, _) in enumerate(all_for_index)}
            for session, log in pending_items:
                idx = index_by_session[session.id]
                line_type = _line_type_for_index(case, idx)
                pending_lines.append(
                    session_line_dict(
                        session,
                        log,
                        case,
                        line_type,
                        included=False,
                        source=SessionLineSource.MANUAL_LATE,
                        extra_flags={"added_late": True, "pending_approval": True},
                    )
                )
                pending_late_inr += pending_lines[-1]["amount_inr"]
                pending_late_count += 1

        included, additional, case_total = compute_case_totals(case, session_lines)
        subtotal += case_total
        total_sessions += len([s for s in session_lines if s.get("included")])

        case_groups.append({
            "case_id": case.id,
            "case_code": case.case_code,
            "child_name": case.child.full_name if case.child else None,
            "billing": case_billing_dict(case),
            "included_sessions": included,
            "additional_sessions": additional,
            "display_included_sessions": _count_display_included(case, session_lines),
            "therapist_share_inr": case_total,
            "pending_late_inr": round(sum(p["amount_inr"] for p in pending_lines), 2),
            "session_lines": session_lines,
            "pending_late_lines": pending_lines,
        })

    leave_deduction, leave_details = compute_leave_deduction(db, therapist_user_id, year, month_num)
    net = max(subtotal - leave_deduction, 0)

    leave_balance = None
    therapist_user = db.get(User, therapist_user_id)
    if therapist_user:
        from app.services import leave_policy_service as policy

        leave_balance = policy.get_leave_balance(db, therapist_user, year=year)

    return {
        "month": f"{year}-{month_num:02d}",
        "month_label": label,
        "therapist_user_id": therapist_user_id,
        "total_sessions": total_sessions,
        "subtotal_inr": round(subtotal, 2),
        "pending_late_inr": round(pending_late_inr, 2),
        "pending_late_count": pending_late_count,
        "leave_deduction_inr": leave_deduction,
        "leave_details": leave_details,
        "leave_balance": leave_balance,
        "net_amount_inr": round(net, 2),
        "cases": case_groups,
    }


def apply_preview_edits(preview: dict, edits: dict) -> dict:
    """Apply therapist edits: exclude approved sessions only."""
    excluded_ids = set(edits.get("exclude_session_ids") or [])

    for case_group in preview["cases"]:
        for line in case_group.get("session_lines", []):
            sid = line.get("session_id")
            if sid and sid in excluded_ids:
                line["included"] = False
                line["flags"] = {**(line.get("flags") or {}), "excluded_by_therapist": True}

    subtotal = 0.0
    total_sessions = 0
    pending_late_inr = 0.0
    pending_late_count = 0
    for case_group in preview["cases"]:
        case = db_case_from_preview(case_group)
        included, additional, case_total = compute_case_totals(case, case_group.get("session_lines", []))
        case_group["included_sessions"] = included
        case_group["additional_sessions"] = additional
        case_group["display_included_sessions"] = _count_display_included(case, case_group.get("session_lines", []))
        case_group["therapist_share_inr"] = case_total
        subtotal += case_total
        total_sessions += len([s for s in case_group.get("session_lines", []) if s.get("included")])
        plines = case_group.get("pending_late_lines", [])
        case_group["pending_late_inr"] = round(sum(p["amount_inr"] for p in plines), 2)
        pending_late_inr += case_group["pending_late_inr"]
        pending_late_count += len(plines)

    preview["subtotal_inr"] = round(subtotal, 2)
    preview["total_sessions"] = total_sessions
    preview["pending_late_inr"] = round(pending_late_inr, 2)
    preview["pending_late_count"] = pending_late_count
    preview["net_amount_inr"] = round(max(preview["subtotal_inr"] - preview["leave_deduction_inr"], 0), 2)
    return preview


def db_case_from_preview(case_group: dict) -> Case:
    """Minimal Case-like object for recomputation from preview billing dict."""
    b = case_group.get("billing") or {}
    case = Case(
        id=case_group["case_id"],
        case_code=case_group["case_code"],
        child_id=0,
        service_type="",
        product_module="",
    )
    if b.get("billing_type"):
        case.billing_type = BillingType(b["billing_type"])
    if b.get("compensation_mode"):
        case.compensation_mode = CompensationMode(b["compensation_mode"])
    case.client_rate_per_session_inr = b.get("client_rate_per_session_inr")
    case.package_session_count = b.get("package_session_count")
    case.package_amount_inr = b.get("package_amount_inr")
    case.pay_share_pct = b.get("pay_share_pct")
    case.therapist_fixed_pay_inr = b.get("therapist_fixed_pay_inr")
    return case


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

    pending_count = int(preview.get("pending_late_count") or 0)
    pending_inr = float(preview.get("pending_late_inr") or 0)
    note_parts = []
    if notes:
        note_parts.append(notes.strip())
    if pending_count:
        note_parts.append(
            f"Contains {pending_count} late-added session(s) pending log approval "
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
    return invoice


def _replace_invoice_lines_from_preview(db: Session, invoice: Invoice, preview: dict) -> None:
    for cl in list(invoice.case_lines):
        db.delete(cl)
    db.flush()

    invoice.amount_inr = preview["net_amount_inr"]
    invoice.subtotal_inr = preview["subtotal_inr"]
    invoice.leave_deduction_inr = preview["leave_deduction_inr"]
    invoice.sessions_count = preview["total_sessions"]

    for case_group in preview["cases"]:
        case_line = InvoiceCaseLine(
            invoice_id=invoice.id,
            case_id=case_group["case_id"],
            case_code=case_group["case_code"],
            billing_type=case_group["billing"].get("billing_type", "PER_SESSION"),
            included_sessions=case_group["included_sessions"],
            additional_sessions=case_group["additional_sessions"],
            therapist_share_inr=case_group["therapist_share_inr"],
            billing_snapshot=case_group["billing"],
        )
        db.add(case_line)
        db.flush()

        for sl in case_group.get("session_lines", []):
            if not sl.get("included"):
                continue
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
                    flags=sl.get("flags") or {},
                )
            )

        for sl in case_group.get("pending_late_lines", []):
            flags = dict(sl.get("flags") or {})
            flags["provisional_amount_inr"] = sl["amount_inr"]
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

    pending_count = int(preview.get("pending_late_count") or 0)
    pending_inr = float(preview.get("pending_late_inr") or 0)
    note_parts = []
    if notes:
        note_parts.append(notes.strip())
    if pending_count:
        note_parts.append(
            f"Contains {pending_count} late-added session(s) pending log approval "
            f"(₹{pending_inr:,.0f} excluded from payout)."
        )
    combined_notes = "\n".join(note_parts) if note_parts else invoice.notes

    _replace_invoice_lines_from_preview(db, invoice, preview)
    invoice.status = InvoiceStatus.IN_REVIEW
    invoice.notes = combined_notes
    return invoice


def invoice_breakdown(db: Session, invoice_id: int) -> dict | None:
    invoice = db.scalars(
        select(Invoice)
        .where(Invoice.id == invoice_id)
        .options(
            selectinload(Invoice.case_lines).selectinload(InvoiceCaseLine.session_lines),
        )
    ).first()
    if not invoice:
        return None

    line_count = sum(len(cl.session_lines) for cl in invoice.case_lines)
    if not invoice.case_lines or line_count == 0:
        preview = build_month_preview(db, invoice.therapist_user_id, invoice.month)
        leave_balance = preview.get("leave_balance")
        return {
            "id": invoice.id,
            "therapist_user_id": invoice.therapist_user_id,
            "month": invoice.month,
            "status": invoice.status.value,
            "subtotal_inr": float(invoice.subtotal_inr or preview["subtotal_inr"]),
            "leave_deduction_inr": float(invoice.leave_deduction_inr or preview["leave_deduction_inr"]),
            "adjustment_inr": float(invoice.adjustment_inr or 0),
            "amount_inr": float(invoice.amount_inr),
            "sessions_count": invoice.sessions_count or preview["total_sessions"],
            "pending_late_inr": preview.get("pending_late_inr", 0),
            "pending_late_count": preview.get("pending_late_count", 0),
            "notes": invoice.notes,
            "reviewer_comment": invoice.reviewer_comment,
            "cases": preview.get("cases") or [],
            "leave_details": preview.get("leave_details") or [],
            "leave_balance": leave_balance,
            "from_preview": True,
        }

    cases = []
    pending_late_inr = 0.0
    pending_late_count = 0
    for cl in invoice.case_lines:
        session_lines = []
        pending_late_lines = []
        for sl in cl.session_lines:
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
                "source": sl.source.value,
                "included": sl.included,
                "flags": flags,
            }
            if is_pending:
                pending_late_lines.append(entry)
                pending_late_inr += float(provisional)
                pending_late_count += 1
            else:
                session_lines.append(entry)

        child_name = None
        case_row = db.get(Case, cl.case_id)
        if case_row and case_row.child:
            child_name = case_row.child.full_name
        cases.append({
            "case_id": cl.case_id,
            "case_code": cl.case_code,
            "child_name": child_name,
            "billing_type": cl.billing_type,
            "included_sessions": cl.included_sessions,
            "additional_sessions": cl.additional_sessions,
            "therapist_share_inr": float(cl.therapist_share_inr),
            "billing_snapshot": cl.billing_snapshot,
            "pending_late_inr": round(sum(float(p["amount_inr"]) for p in pending_late_lines), 2),
            "session_lines": session_lines,
            "pending_late_lines": pending_late_lines,
        })

    return {
        "id": invoice.id,
        "therapist_user_id": invoice.therapist_user_id,
        "month": invoice.month,
        "status": invoice.status.value,
        "subtotal_inr": float(invoice.subtotal_inr or invoice.amount_inr),
        "leave_deduction_inr": float(invoice.leave_deduction_inr or 0),
        "adjustment_inr": float(invoice.adjustment_inr or 0),
        "amount_inr": float(invoice.amount_inr),
        "sessions_count": invoice.sessions_count,
        "pending_late_inr": round(pending_late_inr, 2),
        "pending_late_count": pending_late_count,
        "notes": invoice.notes,
        "reviewer_comment": invoice.reviewer_comment,
        "cases": cases,
    }
