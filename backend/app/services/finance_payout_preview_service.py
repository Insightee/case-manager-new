"""Finance therapist payout preview — therapist × case monthly payout projection."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from sqlalchemy import extract, func, or_, select
from sqlalchemy.orm import Session

from app.models.assignment import CaseAssignment, CaseAssignmentStatus
from app.models.case import BillingType, Case, CompensationMode
from app.models.daily_log import DailyLog, LogApprovalStatus
from app.models.session import Session as TherapySession
from app.models.session import SessionStatus
from app.models.session_absence import SessionAbsenceRequest, SessionAbsenceStatus, SessionAbsenceType
from app.models.therapist_profile import TherapistProfile
from app.models.user import User
from app.services import case_service, leave_policy_service
from app.services.reports_export_helpers import (
    MAX_EXPORT_ROWS,
    is_homecare_case,
    is_shadow_case,
    leave_days_in_month_for_case,
    month_bounds,
    month_long_label,
    scoped_cases,
    user_display_name,
)
from app.services.reports_export_helpers import export_case_id, export_therapist_id

SHADOW_MONTHLY_DAYS = 30


def is_b2b_case(case: Case | None) -> bool:
    mod = ((case.product_module if case else "") or "").lower()
    return "b2b" in mod


def uses_calendar_day_pay(case: Case) -> bool:
    return is_shadow_case(case) or is_b2b_case(case)


def therapist_share_inr(case: Case) -> float:
    """Monthly or per-session therapist share configured on the case."""
    if case.compensation_mode == CompensationMode.FIXED_LUMP:
        return float(case.therapist_fixed_pay_inr or 0)
    return float(case.pay_share_amount_inr or 0)


def client_lumpsum_inr(case: Case) -> float | None:
    """Parent/client charge lump where applicable (package or shadow monthly)."""
    if case.billing_type == BillingType.PACKAGE and case.package_amount_inr:
        return float(case.package_amount_inr)
    if is_shadow_case(case) and case.package_amount_inr:
        return float(case.package_amount_inr)
    return None


def per_session_share_inr(case: Case) -> float:
    share = therapist_share_inr(case)
    if share <= 0:
        return 0.0

    if uses_calendar_day_pay(case):
        return round(share / SHADOW_MONTHLY_DAYS, 2)

    if case.billing_type == BillingType.PER_SESSION:
        return round(share, 2)

    pkg_count = int(case.package_session_count or 0)
    if pkg_count <= 0:
        return 0.0
    return round(share / pkg_count, 2)


def pay_month_day(d: date) -> int:
    """Map calendar date to the 30-day pay-month convention (day 31 → 30)."""
    return min(d.day, SHADOW_MONTHLY_DAYS)


def calendar_days_from_start_day(start_day: int) -> int:
    if start_day <= 1:
        return SHADOW_MONTHLY_DAYS
    return max(SHADOW_MONTHLY_DAYS - start_day + 1, 0)


def calendar_days_outgoing(*, last_log: date, segment_start_day: int) -> int:
    last_day = pay_month_day(last_log)
    if segment_start_day <= 1:
        return last_day
    return max(last_day - segment_start_day + 1, 0)


def calendar_days_incoming(*, first_log: date) -> int:
    return calendar_days_from_start_day(pay_month_day(first_log))


def segment_start_day(
    *,
    assignment_start: date | None,
    employment_start: date | None,
    month_start: date,
    month_end: date,
) -> int:
    start_day = 1
    if employment_start and month_start <= employment_start <= month_end:
        start_day = max(start_day, pay_month_day(employment_start))
    if assignment_start and month_start <= assignment_start <= month_end:
        start_day = max(start_day, pay_month_day(assignment_start))
    return start_day


def calendar_days_for_segment(
    *,
    is_incoming_replacement: bool,
    is_outgoing_replacement: bool,
    first_log: date | None,
    last_log: date | None,
    assignment_start: date | None,
    employment_start: date | None,
    month_start: date,
    month_end: date,
) -> int:
    seg_start = segment_start_day(
        assignment_start=assignment_start,
        employment_start=employment_start,
        month_start=month_start,
        month_end=month_end,
    )

    if is_outgoing_replacement and last_log is not None:
        return calendar_days_outgoing(last_log=last_log, segment_start_day=seg_start)

    if is_incoming_replacement and first_log is not None:
        return calendar_days_incoming(first_log=first_log)

    return calendar_days_from_start_day(seg_start)


def predicted_subtotal_inr(
    case: Case,
    *,
    approved_sessions: int,
    calendar_days: int = SHADOW_MONTHLY_DAYS,
    unpaid_leaves: int = 0,
) -> float:
    share = therapist_share_inr(case)
    if share <= 0:
        return 0.0

    if uses_calendar_day_pay(case):
        effective_days = max(calendar_days - unpaid_leaves, 0)
        return round((share / SHADOW_MONTHLY_DAYS) * effective_days, 2)

    rate = per_session_share_inr(case)
    if rate <= 0:
        return 0.0
    return round(rate * approved_sessions, 2)


@dataclass
class TherapistCaseSegment:
    therapist_user_id: int
    first_log: date | None
    last_log: date | None
    is_incoming_replacement: bool
    is_outgoing_replacement: bool



def _therapists_with_hours_in_month(
    db: Session, case_id: int, start: date, end: date
) -> set[int]:
    rows = db.execute(
        select(TherapySession.therapist_user_id.distinct()).where(
            TherapySession.case_id == case_id,
            TherapySession.status == SessionStatus.COMPLETED,
            TherapySession.scheduled_date >= start,
            TherapySession.scheduled_date <= end,
        )
    ).all()
    return {int(r[0]) for r in rows}


def _assignment_for_month(
    db: Session,
    case_id: int,
    therapist_user_id: int,
    month_start: date,
    month_end: date,
) -> CaseAssignment | None:
    return db.scalars(
        select(CaseAssignment)
        .where(
            CaseAssignment.case_id == case_id,
            CaseAssignment.therapist_user_id == therapist_user_id,
            CaseAssignment.start_date <= month_end,
            or_(
                CaseAssignment.end_date.is_(None),
                CaseAssignment.end_date >= month_start,
            ),
        )
        .order_by(CaseAssignment.start_date.desc())
        .limit(1)
    ).first()


def _is_incoming_replacement(
    db: Session,
    case_id: int,
    therapist_user_id: int,
    month_start: date,
    month_end: date,
) -> bool:
    assignment = _assignment_for_month(
        db, case_id, therapist_user_id, month_start, month_end
    )
    if not assignment:
        return False
    prior = db.scalars(
        select(CaseAssignment.id)
        .where(
            CaseAssignment.case_id == case_id,
            CaseAssignment.therapist_user_id != therapist_user_id,
            CaseAssignment.start_date < assignment.start_date,
        )
        .limit(1)
    ).first()
    return prior is not None


def _is_outgoing_replacement(
    db: Session,
    case_id: int,
    therapist_user_id: int,
    month_start: date,
    month_end: date,
) -> bool:
    assignment = _assignment_for_month(
        db, case_id, therapist_user_id, month_start, month_end
    )
    if not assignment:
        return False
    if assignment.status in (
        CaseAssignmentStatus.TRANSFERRED,
        CaseAssignmentStatus.ENDED,
    ):
        return True
    successor = db.scalars(
        select(CaseAssignment.id)
        .where(
            CaseAssignment.case_id == case_id,
            CaseAssignment.therapist_user_id != therapist_user_id,
            CaseAssignment.start_date > assignment.start_date,
        )
        .limit(1)
    ).first()
    return successor is not None


def _therapist_segments_for_case(
    db: Session, case_id: int, start: date, end: date
) -> list[TherapistCaseSegment]:
    log_rows = db.execute(
        select(
            TherapySession.therapist_user_id,
            func.min(TherapySession.scheduled_date),
            func.max(TherapySession.scheduled_date),
        )
        .join(DailyLog, DailyLog.session_id == TherapySession.id)
        .where(
            TherapySession.case_id == case_id,
            TherapySession.scheduled_date >= start,
            TherapySession.scheduled_date <= end,
            DailyLog.approval_status == LogApprovalStatus.APPROVED.value,
        )
        .group_by(TherapySession.therapist_user_id)
    ).all()

    therapist_ids = {int(r[0]) for r in log_rows}
    hour_only = _therapists_with_hours_in_month(db, case_id, start, end) - therapist_ids

    segments: list[TherapistCaseSegment] = []
    for therapist_id, first_log, last_log in log_rows:
        segments.append(
            TherapistCaseSegment(
                therapist_user_id=int(therapist_id),
                first_log=first_log,
                last_log=last_log,
                is_incoming_replacement=_is_incoming_replacement(
                    db, case_id, int(therapist_id), start, end
                ),
                is_outgoing_replacement=_is_outgoing_replacement(
                    db, case_id, int(therapist_id), start, end
                ),
            )
        )

    for therapist_id in hour_only:
        segments.append(
            TherapistCaseSegment(
                therapist_user_id=therapist_id,
                first_log=None,
                last_log=None,
                is_incoming_replacement=_is_incoming_replacement(
                    db, case_id, therapist_id, start, end
                ),
                is_outgoing_replacement=_is_outgoing_replacement(
                    db, case_id, therapist_id, start, end
                ),
            )
        )

    return segments


def _assignment_start_for_therapist(
    db: Session,
    case_id: int,
    therapist_user_id: int,
    *,
    month_start: date,
    month_end: date,
    reference_date: date | None = None,
) -> date | None:
    """Portal assignment start for the stint active in the billing month."""
    assignment = _assignment_for_month(
        db, case_id, therapist_user_id, month_start, month_end
    )
    if assignment:
        return assignment.start_date
    base = select(CaseAssignment.start_date).where(
        CaseAssignment.case_id == case_id,
        CaseAssignment.therapist_user_id == therapist_user_id,
    )
    if reference_date is not None:
        row = db.scalars(
            base.where(CaseAssignment.start_date <= reference_date)
            .order_by(CaseAssignment.start_date.desc())
            .limit(1)
        ).first()
        if row is not None:
            return row
    return db.scalars(base.order_by(CaseAssignment.start_date.desc()).limit(1)).first()


def _first_session_ever_for_therapist(
    db: Session, case_id: int, therapist_user_id: int
) -> date | None:
    """Earliest session on the case for this therapist (includes manual / forgot-to-log)."""
    return db.scalar(
        select(func.min(TherapySession.scheduled_date)).where(
            TherapySession.case_id == case_id,
            TherapySession.therapist_user_id == therapist_user_id,
        )
    )


def _last_approved_log_for_therapist(
    db: Session, case_id: int, therapist_user_id: int
) -> date | None:
    """Latest approved log date for this therapist on the case (all time)."""
    return db.scalar(
        select(func.max(TherapySession.scheduled_date))
        .join(DailyLog, DailyLog.session_id == TherapySession.id)
        .where(
            TherapySession.case_id == case_id,
            TherapySession.therapist_user_id == therapist_user_id,
            DailyLog.approval_status == LogApprovalStatus.APPROVED.value,
        )
    )


def _employment_start(db: Session, therapist_user_id: int) -> date | None:
    return db.scalars(
        select(TherapistProfile.employment_start_date).where(
            TherapistProfile.user_id == therapist_user_id
        )
    ).first()


def _approved_sessions_for_therapist(
    db: Session, case_id: int, therapist_user_id: int, start: date, end: date
) -> int:
    return int(
        db.scalar(
            select(func.count())
            .select_from(TherapySession)
            .join(DailyLog, DailyLog.session_id == TherapySession.id)
            .where(
                TherapySession.case_id == case_id,
                TherapySession.therapist_user_id == therapist_user_id,
                TherapySession.status == SessionStatus.COMPLETED,
                TherapySession.scheduled_date >= start,
                TherapySession.scheduled_date <= end,
                DailyLog.approval_status == LogApprovalStatus.APPROVED.value,
            )
        )
        or 0
    )


def _approved_absence_for_therapist(
    db: Session, case_id: int, therapist_user_id: int, start: date, end: date
) -> int:
    return int(
        db.scalar(
            select(func.count())
            .select_from(TherapySession)
            .join(
                SessionAbsenceRequest,
                SessionAbsenceRequest.session_id == TherapySession.id,
            )
            .where(
                TherapySession.case_id == case_id,
                TherapySession.therapist_user_id == therapist_user_id,
                TherapySession.status == SessionStatus.CLIENT_ABSENT,
                TherapySession.scheduled_date >= start,
                TherapySession.scheduled_date <= end,
                SessionAbsenceRequest.status == SessionAbsenceStatus.APPROVED,
                SessionAbsenceRequest.absence_type == SessionAbsenceType.CLIENT_ABSENT,
            )
        )
        or 0
    )


def _hours_for_therapist(
    db: Session, case_id: int, therapist_user_id: int, ym: str
) -> float:
    year_s, month_s = ym.split("-")[:2]
    y, m = int(year_s), int(month_s)
    sessions = db.scalars(
        select(TherapySession).where(
            TherapySession.case_id == case_id,
            TherapySession.therapist_user_id == therapist_user_id,
            TherapySession.status == SessionStatus.COMPLETED,
            extract("year", TherapySession.scheduled_date) == y,
            extract("month", TherapySession.scheduled_date) == m,
        )
    ).all()
    total = 0.0
    for s in sessions:
        mins = 0
        if s.actual_start_at and s.actual_end_at:
            mins = int((s.actual_end_at - s.actual_start_at).total_seconds() / 60)
        elif s.start_time and s.end_time:
            start_dt = datetime.combine(s.scheduled_date, s.start_time)
            end_dt = datetime.combine(s.scheduled_date, s.end_time)
            mins = int((end_dt - start_dt).total_seconds() / 60)
        total += mins / 60.0
    return total


def _billable_sessions_for_segment(case: Case, approved: int, child_absence: int) -> int:
    if is_homecare_case(case):
        return approved
    if uses_calendar_day_pay(case):
        return approved + child_absence
    return approved + child_absence


def _leave_for_case_row(db: Session, therapist_id: int, case: Case, ym: str) -> dict[str, int]:
    """Case-scoped leave counts; homecare and shadow/B2B only show linked case leaves."""
    if is_homecare_case(case) or uses_calendar_day_pay(case):
        return leave_days_in_month_for_case(db, therapist_id, case.id, ym)
    return {"paid": 0, "unpaid": 0, "carry_forward": 0}


def payout_preview_row(
    case: Case,
    *,
    ym: str,
    therapist: User,
    approved_sessions: int,
    approved_absence: int,
    billable_sessions: int,
    hours: float,
    calendar_days: int,
    therapist_start_date: date | None,
    case_start_date: date | None,
    case_end_date: date | None,
    leave: dict[str, int],
    leave_credits: int,
) -> dict[str, Any]:
    share = therapist_share_inr(case)
    lumpsum = client_lumpsum_inr(case)
    per_sess = per_session_share_inr(case)
    unpaid = int(leave.get("unpaid", 0))
    subtotal = predicted_subtotal_inr(
        case,
        approved_sessions=approved_sessions,
        calendar_days=calendar_days,
        unpaid_leaves=unpaid if uses_calendar_day_pay(case) else 0,
    )

    return {
        "Month": month_long_label(ym),
        "Case ID": export_case_id(case),
        "Client Name": case_service.case_child_display_name(case) or "",
        "Therapist Name": user_display_name(therapist),
        "Therapist ID": export_therapist_id(therapist),
        "Service Type": case.service_type or case.product_module or "",
        "Therapist Start Date": therapist_start_date.isoformat() if therapist_start_date else "",
        "Case Start Date": case_start_date.isoformat() if case_start_date else "",
        "Case End Date": case_end_date.isoformat() if case_end_date else "",
        "Calendar Days": calendar_days,
        "Approved Sessions": approved_sessions,
        "Approved Absence": approved_absence,
        "Paid Leaves": int(leave.get("paid", 0)),
        "Unpaid Leaves": unpaid,
        "Leave Credits": leave_credits,
        "Total Hours": round(hours, 2),
        "Billable Sessions": billable_sessions,
        "Lumpsum Amount": lumpsum if lumpsum is not None else "",
        "Therapist Share": round(share, 2) if share else "",
        "Per Session Share": per_sess if per_sess else "",
        "Predicted Subtotal": subtotal if subtotal else "",
    }


def payout_preview_rows(
    db: Session,
    ym: str,
    *,
    user: User | None = None,
    product_module: str | None = None,
) -> list[dict[str, Any]]:
    start, end = month_bounds(ym)
    year = int(ym.split("-")[0])

    cases = scoped_cases(db, user, product_module=product_module, active_only=True)
    if not cases:
        return []

    rows: list[dict[str, Any]] = []
    for case in cases[:MAX_EXPORT_ROWS]:
        segments = _therapist_segments_for_case(db, case.id, start, end)
        if not segments:
            continue

        for segment in segments:
            therapist = db.get(User, segment.therapist_user_id)
            if not therapist:
                continue

            approved = _approved_sessions_for_therapist(
                db, case.id, segment.therapist_user_id, start, end
            )
            approved_absence = _approved_absence_for_therapist(
                db, case.id, segment.therapist_user_id, start, end
            )
            hours = _hours_for_therapist(db, case.id, segment.therapist_user_id, ym)

            if approved == 0 and hours <= 0:
                continue

            assignment_start = _assignment_start_for_therapist(
                db,
                case.id,
                segment.therapist_user_id,
                month_start=start,
                month_end=end,
                reference_date=segment.first_log,
            )
            employment_start = _employment_start(db, segment.therapist_user_id)
            case_start = _first_session_ever_for_therapist(
                db, case.id, segment.therapist_user_id
            )
            case_end = (
                _last_approved_log_for_therapist(
                    db, case.id, segment.therapist_user_id
                )
                if segment.is_outgoing_replacement
                else None
            )
            last_log_for_calendar = segment.last_log
            if segment.is_outgoing_replacement and case_end is not None:
                last_log_for_calendar = case_end
            calendar_days = calendar_days_for_segment(
                is_incoming_replacement=segment.is_incoming_replacement,
                is_outgoing_replacement=segment.is_outgoing_replacement,
                first_log=segment.first_log,
                last_log=last_log_for_calendar,
                assignment_start=assignment_start,
                employment_start=employment_start,
                month_start=start,
                month_end=end,
            )

            leave = _leave_for_case_row(db, therapist.id, case, ym)
            balance = leave_policy_service.get_leave_balance(db, therapist, year=year, as_of=end)
            leave_credits = int(
                balance.get("leave_credit_pending", balance.get("paid_remaining", 0)) or 0
            )
            billable = _billable_sessions_for_segment(case, approved, approved_absence)

            rows.append(
                payout_preview_row(
                    case,
                    ym=ym,
                    therapist=therapist,
                    approved_sessions=approved,
                    approved_absence=approved_absence,
                    billable_sessions=billable,
                    hours=hours,
                    calendar_days=calendar_days,
                    therapist_start_date=employment_start,
                    case_start_date=case_start,
                    case_end_date=case_end,
                    leave=leave,
                    leave_credits=leave_credits,
                )
            )

    rows.sort(
        key=lambda r: (
            (r.get("Therapist Name") or "").lower(),
            r.get("Case ID") or "",
        )
    )
    return rows
