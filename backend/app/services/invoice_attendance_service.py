"""Shared month-attendance facts for invoice preview, breakdown, and finance reports."""
from __future__ import annotations

from calendar import monthrange
from datetime import date, time
from enum import Enum
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.case import BillingType, Case
from app.models.daily_log import DailyLog, LogApprovalStatus
from app.models.invoice_line import SessionLineSource, SessionLineType
from app.models.leave import LeaveStatus, TherapistLeave
from app.models.ledger_billing import ProductBillingRule
from app.models.session import Session as TherapySession
from app.models.session import SessionStatus
from app.models.session_absence import SessionAbsenceRequest, SessionAbsenceStatus, SessionAbsenceType
from app.services import finance_payout_preview_service as payout_cycle
from app.services import invoice_billing_service as billing
from app.services import therapist_invoice_labels as labels
from app.services.reports_export_helpers import (
    is_homecare_case,
    is_shadow_case,
    leave_applies_to_case,
    leave_days_in_month,
    leave_days_in_month_for_case,
)


class BillingProfile(str, Enum):
    CALENDAR_DAY = "calendar_day"
    SESSION_BASED = "session_based"


def billing_profile_for_case(case: Case, rule: ProductBillingRule | None = None) -> BillingProfile:
    if payout_cycle.uses_calendar_day_pay(case):
        return BillingProfile.CALENDAR_DAY
    return BillingProfile.SESSION_BASED


def _resolve_rule(db: Session, case: Case) -> ProductBillingRule | None:
    if case.product_billing_rule_id:
        return db.get(ProductBillingRule, case.product_billing_rule_id)
    return db.scalars(
        select(ProductBillingRule)
        .where(
            ProductBillingRule.product_module == case.product_module,
            ProductBillingRule.active.is_(True),
        )
        .order_by(ProductBillingRule.id)
    ).first()


def _month_date_range(year: int, month: int) -> tuple[date, date]:
    last = monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last)


def _child_absence_ui_label(*, payable: bool, consumes_slot: bool, is_shadow: bool = False) -> str:
    del payable, consumes_slot
    return labels.child_away_label(is_shadow=is_shadow, pending=False)


def _pending_reason_tag(*, late: bool) -> str:
    return labels.pending_reason_label(late=late)


def _day_rate_inr(case: Case, *, db: Session | None = None, as_of: date | None = None) -> float:
    share = payout_cycle.therapist_share_inr(case, db=db, as_of=as_of)
    return payout_cycle.per_unit_from_share(case, share)


def _empty_attendance() -> dict[str, int | None]:
    return {
        "approved_sessions": 0,
        "pending_sessions": 0,
        "billable_absence": 0,
        "pending_absence": 0,
        "paid_leaves": None,
        "unpaid_leaves": None,
        "leave_taken": None,
        "pending_leaves": 0,
    }


def _merge_attendance(summary: dict[str, int | None], case_att: dict[str, int | None], profile: BillingProfile) -> None:
    for key in ("approved_sessions", "pending_sessions", "billable_absence", "pending_absence", "pending_leaves"):
        summary[key] = int(summary.get(key) or 0) + int(case_att.get(key) or 0)
    if profile == BillingProfile.CALENDAR_DAY:
        for key in ("paid_leaves", "unpaid_leaves"):
            case_val = case_att.get(key)
            if case_val is None:
                continue
            summary[key] = int(summary.get(key) or 0) + int(case_val)


def _case_has_activity(attendance: dict[str, int | None], pending_lines: list, rejected_for_case: list) -> bool:
    keys = (
        "approved_sessions",
        "pending_sessions",
        "billable_absence",
        "pending_absence",
        "paid_leaves",
        "unpaid_leaves",
        "leave_taken",
        "pending_leaves",
    )
    if any(int(attendance.get(k) or 0) > 0 for k in keys):
        return True
    return bool(pending_lines or rejected_for_case)


def fetch_pending_submitted_sessions(
    db: Session,
    therapist_user_id: int,
    year: int,
    month: int,
) -> list[tuple[TherapySession, DailyLog, Case]]:
    """Submitted on time, log still PENDING (not late_addition)."""
    start, end = _month_date_range(year, month)
    stmt = (
        select(TherapySession)
        .join(DailyLog, DailyLog.session_id == TherapySession.id)
        .where(
            TherapySession.therapist_user_id == therapist_user_id,
            TherapySession.status == SessionStatus.COMPLETED,
            TherapySession.scheduled_date >= start,
            TherapySession.scheduled_date <= end,
            DailyLog.approval_status == LogApprovalStatus.PENDING,
            DailyLog.late_addition.is_(False),
        )
        .options(selectinload(TherapySession.case).selectinload(Case.child))
        .order_by(TherapySession.scheduled_date, TherapySession.start_time)
    )
    result: list[tuple[TherapySession, DailyLog, Case]] = []
    for session in db.scalars(stmt).all():
        if session.daily_log and session.case and session.case.billing_type:
            result.append((session, session.daily_log, session.case))
    return result


def fetch_rejected_sessions(
    db: Session,
    therapist_user_id: int,
    year: int,
    month: int,
) -> list[tuple[TherapySession, DailyLog, Case]]:
    start, end = _month_date_range(year, month)
    stmt = (
        select(TherapySession)
        .join(DailyLog, DailyLog.session_id == TherapySession.id)
        .where(
            TherapySession.therapist_user_id == therapist_user_id,
            TherapySession.scheduled_date >= start,
            TherapySession.scheduled_date <= end,
            DailyLog.approval_status == LogApprovalStatus.REJECTED,
        )
        .options(selectinload(TherapySession.case).selectinload(Case.child))
        .order_by(TherapySession.scheduled_date, TherapySession.start_time)
    )
    return [
        (s, s.daily_log, s.case)
        for s in db.scalars(stmt).all()
        if s.daily_log and s.case and s.case.billing_type
    ]


def fetch_child_absence_requests(
    db: Session,
    therapist_user_id: int,
    year: int,
    month: int,
) -> list[tuple[SessionAbsenceRequest, TherapySession, Case]]:
    start, end = _month_date_range(year, month)
    stmt = (
        select(SessionAbsenceRequest)
        .join(TherapySession, SessionAbsenceRequest.session_id == TherapySession.id)
        .where(
            SessionAbsenceRequest.therapist_user_id == therapist_user_id,
            SessionAbsenceRequest.absence_type == SessionAbsenceType.CLIENT_ABSENT,
            TherapySession.scheduled_date >= start,
            TherapySession.scheduled_date <= end,
        )
        .options(
            selectinload(SessionAbsenceRequest.session),
            selectinload(SessionAbsenceRequest.case).selectinload(Case.child),
        )
        .order_by(TherapySession.scheduled_date, TherapySession.start_time)
    )
    rows: list[tuple[SessionAbsenceRequest, TherapySession, Case]] = []
    for req in db.scalars(stmt).all():
        if req.session and req.case and req.case.billing_type:
            rows.append((req, req.session, req.case))
    return rows


def fetch_leaves_for_month(
    db: Session,
    therapist_user_id: int,
    year: int,
    month: int,
) -> list[TherapistLeave]:
    start, end = _month_date_range(year, month)
    return list(
        db.scalars(
            select(TherapistLeave).where(
                TherapistLeave.therapist_user_id == therapist_user_id,
                TherapistLeave.start_date <= end,
                TherapistLeave.end_date >= start,
            )
        ).all()
    )


def _leave_days_in_month(leave: TherapistLeave, start: date, end: date) -> int:
    overlap_start = max(leave.start_date, start)
    overlap_end = min(leave.end_date, end)
    if overlap_end < overlap_start:
        return 0
    return (overlap_end - overlap_start).days + 1


def _child_absence_policy(rule: ProductBillingRule | None) -> tuple[bool, bool]:
    payable = bool(rule and getattr(rule, "child_absent_therapist_payable", False))
    consumes = bool(rule and getattr(rule, "package_consumes_on_child_absent", False))
    return payable, consumes


def _child_absence_amount(
    case: Case,
    line_type: SessionLineType,
    *,
    db: Session | None = None,
    as_of: date | None = None,
) -> float:
    return billing.compute_session_line_amount(case, line_type, db=db, as_of=as_of)


def _sort_key_session(session: TherapySession) -> tuple:
    return (session.scheduled_date, session.start_time or time.min, session.id)


def _slot_consuming_before(
    consuming_absences: list[tuple[date, time | None]],
    session: TherapySession,
) -> int:
    session_key = _sort_key_session(session)
    count = 0
    for abs_date, abs_time in consuming_absences:
        abs_key = (abs_date, abs_time or time.min, 0)
        if abs_key < session_key[:2] + (0,):
            count += 1
        elif abs_date == session.scheduled_date and (abs_time or time.min) <= (session.start_time or time.min):
            count += 1
    return count


def build_child_absence_line(
    req: SessionAbsenceRequest,
    session: TherapySession,
    case: Case,
    rule: ProductBillingRule | None,
    *,
    package_index: int | None = None,
    db: Session | None = None,
) -> dict[str, Any]:
    del package_index
    payable, consumes = _child_absence_policy(rule)
    as_of = session.scheduled_date
    shadow = is_shadow_case(case) or payout_cycle.uses_calendar_day_pay(case)
    # Therapist invoice: child away is always Session cancelled @ ₹0 (homecare + shadow).
    # Homecare also never consumes package slots for pay.
    if is_homecare_case(case) and not shadow:
        payable = False
        consumes = False
    del payable

    if req.status == SessionAbsenceStatus.PENDING_APPROVAL:
        return {
            "session_id": session.id,
            "absence_request_id": req.id,
            "session_date": session.scheduled_date.isoformat(),
            "line_type": SessionLineType.INCLUDED.value,
            "ui_label": labels.child_away_label(is_shadow=shadow, pending=True),
            "amount_inr": 0.0,
            "display_amount_inr": 0.0,
            "included": False,
            "affects_net": False,
            "breakdown_bucket": labels.BUCKET_PENDING,
            "status_tag": labels.PENDING_TAG,
            "consumes_package_slot": consumes,
            "approval_status": req.status.value,
            "reason": req.reason,
            "pending_reason": labels.PENDING_TAG,
            "line_kind": "PENDING_ABSENCE",
            "flags": {"pending_approval": True, "pending_reason": labels.PENDING_TAG},
        }

    # Approved (payable or not) and other terminal states — cancelled @ ₹0 on the statement.
    return {
        "session_id": session.id,
        "absence_request_id": req.id,
        "session_date": session.scheduled_date.isoformat(),
        "line_type": SessionLineType.INCLUDED.value,
        "ui_label": labels.child_away_label(is_shadow=shadow, pending=False),
        "amount_inr": 0.0,
        "display_amount_inr": 0.0,
        "included": False,
        "affects_net": False,
        "counts_toward_monthly": bool(shadow),
        "breakdown_bucket": labels.BUCKET_INFO,
        "status_tag": None,
        "consumes_package_slot": False,
        "approval_status": req.status.value,
        "reason": req.reason,
        "line_kind": "CHILD_AWAY",
    }


def _line_type_for_package_index(case: Case, index: int) -> SessionLineType:
    if case.billing_type == BillingType.PER_SESSION:
        return SessionLineType.PER_SESSION
    pkg_count = int(case.package_session_count or 0)
    return SessionLineType.INCLUDED if index < pkg_count else SessionLineType.ADDITIONAL


def build_pending_approval_line(
    session: TherapySession,
    log: DailyLog,
    case: Case,
    *,
    package_index: int,
    db: Session | None = None,
) -> dict[str, Any]:
    line_type = _line_type_for_package_index(case, package_index)
    late = bool(log.late_addition)
    reason = _pending_reason_tag(late=late)
    line = billing.session_line_dict(
        session,
        log,
        case,
        line_type,
        included=False,
        source=SessionLineSource.MANUAL_LATE if late else SessionLineSource.LOG,
        extra_flags={
            "added_late": late,
            "pending_approval": True,
            "pending_reason": reason,
        },
        db=db,
    )
    line["ui_label"] = labels.session_completed_label(line_type=line_type.value)
    line["display_amount_inr"] = line.get("amount_inr")
    line["affects_net"] = False
    line["breakdown_bucket"] = labels.BUCKET_PENDING
    line["status_tag"] = labels.PENDING_TAG
    line["line_kind"] = "PENDING_LATE" if late else "PENDING_LOG"
    line["pending_reason"] = reason
    return line


def _iter_leave_dates(
    leave: TherapistLeave,
    start: date,
    end: date,
    db: Session | None = None,
    case_id: int | None = None,
) -> list[date]:
    if db is not None:
        from app.services import leave_dates_service as leave_dates

        return leave_dates.billable_leave_dates(
            db, leave, case_id=case_id, from_date=start, to_date=end
        )
    overlap_start = max(leave.start_date, start)
    overlap_end = min(leave.end_date, end)
    if overlap_end < overlap_start:
        return []
    out: list[date] = []
    cur = overlap_start
    while cur <= overlap_end:
        out.append(cur)
        cur = date.fromordinal(cur.toordinal() + 1)
    return out


def build_leave_lines_for_case(
    db: Session,
    *,
    case: Case,
    leaves: list[TherapistLeave],
    month_start: date,
    month_end: date,
) -> list[dict[str, Any]]:
    """Session-wise leave rows for invoice clarity.

    Shadow: paid leave shows day rate (still paid); unpaid shows −day rate.
    Homecare: informational only — session cancelled, not billed (no leave math).
    """
    shadow = is_shadow_case(case) or payout_cycle.uses_calendar_day_pay(case)
    day_rate = _day_rate_inr(case, db=db, as_of=month_end)
    lines: list[dict[str, Any]] = []

    from app.services.leave_policy_service import _paid_unpaid_for_leave

    for lv in leaves:
        dates = _iter_leave_dates(
            lv, month_start, month_end, db=db if shadow else None, case_id=case.id if shadow else None
        )
        if lv.status == LeaveStatus.PENDING:
            for d in dates:
                if not shadow:
                    lines.append(
                        {
                            "leave_id": lv.id,
                            "session_date": d.isoformat(),
                            "duration_minutes": 0,
                            "line_type": SessionLineType.INCLUDED.value,
                            "ui_label": labels.leave_label(is_shadow=False, paid=False, pending=False),
                            "amount_inr": 0.0,
                            "display_amount_inr": 0.0,
                            "included": False,
                            "affects_net": False,
                            "breakdown_bucket": labels.BUCKET_INFO,
                            "status_tag": None,
                            "line_kind": "LEAVE_CANCELLED",
                            "flags": {"homecare_leave": True, "leave_pending_elsewhere": True},
                        }
                    )
                    continue
                lines.append(
                    {
                        "leave_id": lv.id,
                        "session_date": d.isoformat(),
                        "duration_minutes": 0,
                        "line_type": SessionLineType.INCLUDED.value,
                        "ui_label": labels.leave_label(is_shadow=True, paid=False, pending=True),
                        "amount_inr": 0.0,
                        "display_amount_inr": 0.0,
                        "included": False,
                        "affects_net": False,
                        "breakdown_bucket": labels.BUCKET_PENDING,
                        "status_tag": labels.PENDING_TAG,
                        "line_kind": "PENDING_LEAVE",
                        "flags": {"pending_approval": True, "pending_reason": labels.PENDING_TAG},
                    }
                )
            continue
        if lv.status != LeaveStatus.APPROVED:
            continue

        year = month_start.year
        paid_days, unpaid_days = _paid_unpaid_for_leave(db, lv, year)
        if not dates:
            continue

        all_dates = _iter_leave_dates(
            lv, lv.start_date, lv.end_date, db=db if shadow else None, case_id=case.id if shadow else None
        )
        paid_n = max(0, int(lv.paid_days or 0))
        if unpaid_days <= 0:
            paid_left = len(dates)
        elif paid_days <= 0:
            paid_left = 0
        else:
            paid_left = sum(1 for d in dates if d in all_dates and all_dates.index(d) < paid_n)
        if not shadow:
            for d in dates:
                lines.append(
                    {
                        "leave_id": lv.id,
                        "session_date": d.isoformat(),
                        "duration_minutes": 0,
                        "line_type": SessionLineType.INCLUDED.value,
                        "ui_label": labels.leave_label(is_shadow=False, paid=False),
                        "amount_inr": 0.0,
                        "display_amount_inr": 0.0,
                        "included": False,
                        "affects_net": False,
                        "breakdown_bucket": labels.BUCKET_INFO,
                        "status_tag": None,
                        "line_kind": "LEAVE_CANCELLED",
                        "flags": {"homecare_leave": True},
                    }
                )
            continue

        for idx, d in enumerate(dates):
            is_paid = idx < paid_left
            if is_paid:
                lines.append(
                    {
                        "leave_id": lv.id,
                        "session_date": d.isoformat(),
                        "duration_minutes": 0,
                        "line_type": SessionLineType.INCLUDED.value,
                        "ui_label": labels.leave_label(is_shadow=True, paid=True),
                        "amount_inr": 0.0,
                        "display_amount_inr": 0.0,
                        "included": False,
                        "affects_net": False,
                        "counts_toward_monthly": True,
                        "breakdown_bucket": labels.BUCKET_IN_PAY,
                        "status_tag": None,
                        "line_kind": "PAID_LEAVE",
                        "flags": {"paid_leave": True},
                    }
                )
            else:
                lines.append(
                    {
                        "leave_id": lv.id,
                        "session_date": d.isoformat(),
                        "duration_minutes": 0,
                        "line_type": SessionLineType.INCLUDED.value,
                        "ui_label": labels.leave_label(is_shadow=True, paid=False),
                        "amount_inr": -day_rate,
                        "display_amount_inr": -day_rate,
                        "included": False,
                        "affects_net": True,
                        "breakdown_bucket": labels.BUCKET_IN_PAY,
                        "status_tag": None,
                        "line_kind": "UNPAID_LEAVE",
                        "flags": {"unpaid_leave": True},
                    }
                )
    return lines


def leave_service_day_count(leave: TherapistLeave) -> int:
    from app.services import leave_service

    return leave_service.leave_day_count(leave.start_date, leave.end_date) or 0


def compute_leave_deduction_inr(
    db: Session,
    therapist_user_id: int,
    ym: str,
    cases: list[Case],
) -> float:
    """Unpaid approved leave deduction for calendar-day cases only."""
    total = 0.0
    year, month_num = int(ym[:4]), int(ym[5:7])
    _start, month_end = _month_date_range(year, month_num)
    for case in cases:
        if billing_profile_for_case(case) != BillingProfile.CALENDAR_DAY:
            continue
        leave_counts = leave_days_in_month_for_case(db, therapist_user_id, case.id, ym)
        unpaid = int(leave_counts.get("unpaid", 0))
        if unpaid <= 0:
            continue
        segment = payout_cycle.segment_for_therapist(db, case, therapist_user_id, ym)
        calendar_days = segment.calendar_days if segment else payout_cycle.SHADOW_MONTHLY_DAYS
        approved_sessions = segment.approved_sessions if segment else 0
        gross_before = payout_cycle.predicted_subtotal_inr(
            case,
            approved_sessions=approved_sessions,
            calendar_days=calendar_days,
            unpaid_leaves=0,
            db=db,
            as_of=month_end,
        )
        gross_after = payout_cycle.predicted_subtotal_inr(
            case,
            approved_sessions=approved_sessions,
            calendar_days=calendar_days,
            unpaid_leaves=unpaid,
            db=db,
            as_of=month_end,
        )
        total += max(gross_before - gross_after, 0.0)
    return round(total, 2)


def month_attendance_facts(
    db: Session,
    *,
    therapist_user_id: int,
    ym: str,
    case: Case | None = None,
) -> dict[str, Any]:
    year, month_num = int(ym[:4]), int(ym[5:7])
    start, end = _month_date_range(year, month_num)

    from app.models.assignment import CaseAssignment, CaseAssignmentStatus

    assigned_cases = billing._assigned_billing_cases(db, therapist_user_id)
    if case is not None:
        assigned_cases = [c for c in assigned_cases if c.id == case.id]

    approved = billing.fetch_billable_sessions(db, therapist_user_id, year, month_num)
    pending_late = billing.fetch_pending_late_sessions(db, therapist_user_id, year, month_num)
    pending_submitted = fetch_pending_submitted_sessions(db, therapist_user_id, year, month_num)
    rejected_sessions = fetch_rejected_sessions(db, therapist_user_id, year, month_num)
    absence_rows = fetch_child_absence_requests(db, therapist_user_id, year, month_num)
    leaves = fetch_leaves_for_month(db, therapist_user_id, year, month_num)

    by_case_id: dict[int, Case] = {c.id: c for c in assigned_cases}
    for _, _, c in approved + pending_late + pending_submitted + rejected_sessions:
        by_case_id[c.id] = c
    for _, _, c in absence_rows:
        by_case_id[c.id] = c

    rejected_notes: list[dict[str, Any]] = []
    case_payloads: list[dict[str, Any]] = []
    summary = _empty_attendance()

    for case_id, case_row in by_case_id.items():
        rule = _resolve_rule(db, case_row)
        profile = billing_profile_for_case(case_row, rule)

        case_approved = [(s, l) for s, l, c in approved if c.id == case_id]
        case_pending_late = [(s, l) for s, l, c in pending_late if c.id == case_id]
        case_pending_submitted = [(s, l) for s, l, c in pending_submitted if c.id == case_id]
        case_rejected = [(s, l) for s, l, c in rejected_sessions if c.id == case_id]
        case_absences = [(r, s) for r, s, c in absence_rows if c.id == case_id]
        case_leaves = [
            lv
            for lv in leaves
            if leave_applies_to_case(lv, case_id) or (not lv.case_id and not lv.case_ids)
        ]

        attendance = _empty_attendance()
        if profile == BillingProfile.CALENDAR_DAY:
            leave_counts = leave_days_in_month_for_case(db, therapist_user_id, case_id, ym)
            paid = int(leave_counts.get("paid", 0))
            unpaid = int(leave_counts.get("unpaid", 0))
            attendance["paid_leaves"] = paid if paid > 0 else None
            attendance["unpaid_leaves"] = unpaid if unpaid > 0 else None
        else:
            taken = sum(
                _leave_days_in_month(lv, start, end)
                for lv in case_leaves
                if lv.status == LeaveStatus.APPROVED
            )
            attendance["leave_taken"] = taken if taken > 0 else None

        attendance["pending_leaves"] = sum(
            _leave_days_in_month(lv, start, end)
            for lv in case_leaves
            if lv.status == LeaveStatus.PENDING
        )

        for lv in leaves:
            if profile == BillingProfile.CALENDAR_DAY and not leave_applies_to_case(lv, case_id):
                continue
            if profile == BillingProfile.SESSION_BASED and lv not in case_leaves:
                continue
            if lv.status == LeaveStatus.REJECTED:
                rejected_notes.append(
                    {
                        "type": "leave",
                        "date": lv.start_date.isoformat(),
                        "case_code": case_row.case_code,
                        "child_name": case_row.child.full_name if case_row.child else None,
                        "reason": lv.reason,
                        "status": lv.status.value,
                    }
                )
            elif lv.status == LeaveStatus.CANCELLED:
                rejected_notes.append(
                    {
                        "type": "leave",
                        "date": lv.start_date.isoformat(),
                        "case_code": case_row.case_code,
                        "child_name": case_row.child.full_name if case_row.child else None,
                        "reason": lv.reason or "Cancelled",
                        "status": "cancelled",
                    }
                )

        for session, log in case_rejected:
            rejected_notes.append(
                {
                    "type": "session_log",
                    "date": session.scheduled_date.isoformat(),
                    "case_code": case_row.case_code,
                    "child_name": case_row.child.full_name if case_row.child else None,
                    "reason": log.late_reason or log.observations,
                    "status": log.approval_status.value if hasattr(log.approval_status, "value") else str(log.approval_status),
                }
            )

        consuming_absences: list[tuple[date, time | None]] = []
        child_absence_lines: list[dict[str, Any]] = []
        pending_approval_lines: list[dict[str, Any]] = []

        approved_absence_sorted = sorted(
            [(r, s) for r, s in case_absences if r.status == SessionAbsenceStatus.APPROVED],
            key=lambda x: _sort_key_session(x[1]),
        )
        payable, consumes_policy = _child_absence_policy(rule)
        # Homecare never pays or consumes slots for child away — actual sessions only.
        if is_homecare_case(case_row) and not (
            is_shadow_case(case_row) or payout_cycle.uses_calendar_day_pay(case_row)
        ):
            payable, consumes_policy = False, False
        package_slot_index = 0
        for req, session in approved_absence_sorted:
            if payable and consumes_policy:
                line = build_child_absence_line(
                    req, session, case_row, rule, package_index=package_slot_index, db=db
                )
                package_slot_index += 1
                consuming_absences.append((session.scheduled_date, session.start_time))
            else:
                line = build_child_absence_line(req, session, case_row, rule, db=db)
            child_absence_lines.append(line)
            if line.get("included"):
                attendance["billable_absence"] += 1

        for req, session in case_absences:
            if req.status == SessionAbsenceStatus.PENDING_APPROVAL:
                line = build_child_absence_line(req, session, case_row, rule, db=db)
                child_absence_lines.append(line)
                attendance["pending_absence"] += 1
            elif req.status == SessionAbsenceStatus.REJECTED:
                rejected_notes.append(
                    {
                        "type": "child_absence",
                        "date": session.scheduled_date.isoformat(),
                        "case_code": case_row.case_code,
                        "child_name": case_row.child.full_name if case_row.child else None,
                        "reason": req.reason,
                        "status": req.status.value,
                    }
                )

        leave_lines = build_leave_lines_for_case(
            db,
            case=case_row,
            leaves=case_leaves,
            month_start=start,
            month_end=end,
        )
        # Pending leave days also count toward pending_leaves (already set).

        all_pending = sorted(
            case_pending_late + case_pending_submitted,
            key=lambda x: (x[0].scheduled_date, x[0].start_time or time.min),
        )
        all_for_index = sorted(
            case_approved + [(s, l) for s, l in all_pending],
            key=lambda x: (x[0].scheduled_date, x[0].start_time or time.min),
        )
        index_by_session = {s.id: i for i, (s, _) in enumerate(all_for_index)}

        for session, log in all_pending:
            base_index = index_by_session.get(session.id, 0)
            offset = _slot_consuming_before(consuming_absences, session)
            pending_approval_lines.append(
                build_pending_approval_line(
                    session, log, case_row, package_index=base_index + offset, db=db
                )
            )

        session_lines = []
        if case_approved:
            ordered = sorted(case_approved, key=lambda x: (x[0].scheduled_date, x[0].start_time or time.min))
            regular_items = [(s, l) for s, l in ordered if not l.transition_id]
            transition_items = [(s, l) for s, l in ordered if l.transition_id]
            for idx, (session, log) in enumerate(regular_items):
                offset = _slot_consuming_before(consuming_absences, session)
                line_type = _line_type_for_package_index(case_row, idx + offset)
                line = billing.session_line_dict(session, log, case_row, line_type, db=db)
                line["ui_label"] = labels.session_completed_label(line_type=line_type.value)
                line["display_amount_inr"] = line.get("amount_inr")
                line["affects_net"] = True
                line["breakdown_bucket"] = labels.BUCKET_IN_PAY
                line["line_kind"] = "SESSION"
                session_lines.append(line)
            for session, log in transition_items:
                line = billing.session_line_dict(
                    session, log, case_row, SessionLineType.PER_SESSION, db=db
                )
                line["ui_label"] = labels.session_completed_label(line_type=SessionLineType.PER_SESSION.value)
                line["display_amount_inr"] = line.get("amount_inr")
                line["affects_net"] = True
                line["breakdown_bucket"] = labels.BUCKET_IN_PAY
                line["line_kind"] = "SESSION"
                session_lines.append(line)

        attendance["approved_sessions"] = len([l for l in session_lines if l.get("included", True)])
        attendance["pending_sessions"] = len(pending_approval_lines)

        case_rejected_notes = [n for n in rejected_notes if n.get("case_code") == case_row.case_code]
        has_activity = _case_has_activity(attendance, pending_approval_lines, case_rejected_notes)

        _merge_attendance(summary, attendance, profile)

        case_payloads.append(
            {
                "case_id": case_id,
                "billing_profile": profile.value,
                "has_activity": has_activity,
                "attendance": attendance,
                "pending_approval_lines": pending_approval_lines,
                "child_absence_lines": child_absence_lines,
                "leave_lines": leave_lines,
                "session_lines": session_lines,
                "consuming_absences": consuming_absences,
            }
        )

    has_calendar = any(billing_profile_for_case(c) == BillingProfile.CALENDAR_DAY for c in by_case_id.values())
    has_session = any(billing_profile_for_case(c) == BillingProfile.SESSION_BASED for c in by_case_id.values())
    if not has_calendar:
        summary["paid_leaves"] = None
        summary["unpaid_leaves"] = None
    elif not (int(summary.get("paid_leaves") or 0) or int(summary.get("unpaid_leaves") or 0)):
        summary["paid_leaves"] = None
        summary["unpaid_leaves"] = None
    if has_session:
        approved_leave_days = sum(
            _leave_days_in_month(lv, start, end) for lv in leaves if lv.status == LeaveStatus.APPROVED
        )
        summary["leave_taken"] = approved_leave_days if approved_leave_days > 0 else None
    else:
        summary["leave_taken"] = None

    leave_deduction_inr = compute_leave_deduction_inr(
        db, therapist_user_id, ym, list(by_case_id.values())
    )

    return {
        "attendance_summary": summary,
        "leave_deduction_inr": leave_deduction_inr,
        "rejected_notes": rejected_notes,
        "cases": case_payloads,
    }
