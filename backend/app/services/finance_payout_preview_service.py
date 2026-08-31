"""Finance therapist payout preview — therapist × case monthly payout projection."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from sqlalchemy import extract, func, or_, select
from sqlalchemy.orm import Session

from app.core.billing_validation import resolve_therapist_pay
from app.models.assignment import CaseAssignment, CaseAssignmentStatus
from app.models.case import BillingType, Case, CaseStatus, CompensationMode
from app.models.case_therapist_transition import CaseTherapistTransitionDay
from app.models.daily_log import DailyLog, LogApprovalStatus
from app.models.session import Session as TherapySession
from app.models.session import SessionStatus
from app.models.session_absence import SessionAbsenceRequest, SessionAbsenceStatus, SessionAbsenceType
from app.models.therapist_profile import TherapistProfile
from app.models.user import User
from app.services import case_service, leave_policy_service
from app.services.reports_export_helpers import (
    MAX_EXPORT_ROWS,
    case_people_export_fields,
    is_homecare_case,
    is_shadow_case,
    leave_days_in_month_for_case,
    month_bounds,
    month_long_label,
    parent_by_child,
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


def therapist_share_inr(case: Case, *, db: Session | None = None, as_of: date | None = None) -> float:
    """Monthly or per-session therapist share configured on the case (INR lumpsum).

    When db + as_of are provided, resolve from billing rate history so a future hike
    on the case does not rewrite past month payouts.
    """
    if db is not None and as_of is not None:
        from app.services import billing_rate_history_service

        return billing_rate_history_service.resolve_therapist_pay_as_of(db, case, as_of)
    return resolve_therapist_pay(case)


def client_lumpsum_inr(case: Case) -> float | None:
    """Configured client billing amount for finance payout preview exports.

    Matches case billing: package/monthly period charge, or per-session client rate.
    Shown as ``Client Amount (INR)`` (legacy header ``Lumpsum Amount`` remapped on read).
    """
    amount = float(client_configured_share_inr(case) or 0)
    return round(amount, 2) if amount > 0 else None


def per_unit_from_share(case: Case, share: float) -> float:
    """Per-day (shadow/B2B) or per-session (homecare) unit from a monthly/session lump."""
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


def per_session_share_inr(case: Case) -> float:
    return per_unit_from_share(case, therapist_share_inr(case))


def client_configured_share_inr(case: Case) -> float:
    """Client allotment amount: monthly/package lump or per-session rate."""
    if uses_calendar_day_pay(case):
        if case.package_amount_inr:
            return float(case.package_amount_inr)
        if case.client_monthly_rate_inr:
            return float(case.client_monthly_rate_inr)
        if case.client_rate_per_session_inr:
            return round(float(case.client_rate_per_session_inr) * SHADOW_MONTHLY_DAYS, 2)
        return 0.0
    if case.billing_type == BillingType.PER_SESSION:
        return float(case.client_rate_per_session_inr or 0)
    if case.billing_type == BillingType.MONTHLY_FIXED:
        return float(case.client_monthly_rate_inr or case.package_amount_inr or 0)
    return float(case.package_amount_inr or 0)


def pay_month_day(d: date) -> int:
    """Map calendar date to the 30-day pay-month convention (day 31 → 30)."""
    return min(d.day, SHADOW_MONTHLY_DAYS)


def calendar_days_from_start_day(start_day: int) -> int:
    if start_day <= 1:
        return SHADOW_MONTHLY_DAYS
    return max(SHADOW_MONTHLY_DAYS - start_day + 1, 0)


def calendar_days_outgoing(*, last_log: date, segment_start_day: int) -> int:
    """Inclusive pay-month days through ``last_log``'s calendar day (capped at 30).

    ``last_log`` is a *date whose .day is the earning boundary in the pay month*,
    not a cross-month timestamp. Callers must clamp out-of-month dates first.
    """
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


def clamp_pay_month_bound_end(
    *,
    bound_end: date,
    last_log: date | None,
    month_start: date,
    month_end: date,
) -> date | None:
    """Non-expansive earning end for ``calendar_days_outgoing``.

    Outgoing Shadow/B2B already stops at last approved-log scheduled date.
    This clamp only prevents an out-of-month date's ``.day`` from being read as
    a day-of-the-pay-month (e.g. 3 July → 3 days in June).

    Returns ``None`` when there is no in-month evidence (caller must pay 0).
    Does not invent days beyond ``min(last_log, month_end)``.
    """
    in_month_log = _in_month_approved_log(last_log, month_start, month_end)
    if bound_end < month_start:
        return None
    if bound_end > month_end:
        if in_month_log is None:
            return None
        return min(in_month_log, month_end)
    return bound_end


def _in_month_approved_log(
    last_log: date | None, month_start: date, month_end: date
) -> date | None:
    """In-month approved-log scheduled_date, or None if missing / wrong month."""
    if last_log is None or last_log < month_start or last_log > month_end:
        return None
    return last_log


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
    segment_end: date | None = None,
) -> int:
    """Inclusive pay-month days for a therapist×case segment.

    - Start→mid / mid→mid with a known end: ``end_day - start_day + 1``
    - Mid→end (incoming, no end): from first/start through day 30
    - Full / mid-start ongoing: from segment start through day 30

    ``last_log`` / ``first_log`` are in-month ``sessions.scheduled_date`` of an
    approved non-transition daily log. Ongoing Shadow/B2B does **not** require a
    log on every payable day; outgoing segments already use last approved-log
    date as the earning boundary. ``seg_start`` is never adjusted here.
    """
    seg_start = segment_start_day(
        assignment_start=assignment_start,
        employment_start=employment_start,
        month_start=month_start,
        month_end=month_end,
    )
    if is_incoming_replacement and first_log is not None:
        seg_start = max(seg_start, pay_month_day(first_log))

    bound_end = segment_end
    if bound_end is None and is_outgoing_replacement:
        bound_end = last_log
    if bound_end is not None:
        effective_end = clamp_pay_month_bound_end(
            bound_end=bound_end,
            last_log=last_log,
            month_start=month_start,
            month_end=month_end,
        )
        if effective_end is None:
            return 0
        return calendar_days_outgoing(last_log=effective_end, segment_start_day=seg_start)

    if is_incoming_replacement and first_log is not None:
        return calendar_days_from_start_day(seg_start)

    return calendar_days_from_start_day(seg_start)


def _case_status_end_in_month(case: Case, month_start: date, month_end: date) -> date | None:
    if case.status not in (
        CaseStatus.CLOSED,
        CaseStatus.DEACTIVATED,
        CaseStatus.SUSPENDED,
    ):
        return None
    effective = case.status_effective_date
    if effective is None or not (month_start <= effective <= month_end):
        return None
    return effective


def _resolve_segment_end(
    *,
    case: Case,
    assignment: CaseAssignment | None,
    is_outgoing_replacement: bool,
    last_log: date | None,
    last_approved_ever: date | None,
    month_start: date,
    month_end: date,
) -> date | None:
    """Official end of a bounded segment (replacement exit, assignment end, or case close).

    Outgoing replacement: last approved non-transition log ``scheduled_date``
    (all-time, then in-month). That date is the earning boundary; it is **not**
    assignment.end_date. ``calendar_days_for_segment`` clamps it into the pay month.
    """
    if is_outgoing_replacement:
        return last_approved_ever or last_log

    candidates: list[date] = []
    if assignment and assignment.end_date is not None:
        if month_start <= assignment.end_date <= month_end:
            candidates.append(assignment.end_date)
    status_end = _case_status_end_in_month(case, month_start, month_end)
    if status_end is not None:
        candidates.append(status_end)
    if not candidates:
        return None
    return min(candidates)


def predicted_amount_inr(
    case: Case,
    *,
    share: float,
    approved_sessions: int,
    calendar_days: int = SHADOW_MONTHLY_DAYS,
    unpaid_leaves: int = 0,
) -> float:
    """Payout-report money rule with an injected lump (therapist share or client allotment)."""
    if share <= 0:
        return 0.0
    if uses_calendar_day_pay(case):
        effective_days = max(int(calendar_days) - int(unpaid_leaves), 0)
        return round((share / SHADOW_MONTHLY_DAYS) * effective_days, 2)
    if case.billing_type == BillingType.MONTHLY_FIXED:
        return round(share, 2) if int(approved_sessions) > 0 else 0.0
    rate = per_unit_from_share(case, share)
    if rate <= 0:
        return 0.0
    return round(rate * int(approved_sessions), 2)


def predicted_subtotal_inr(
    case: Case,
    *,
    approved_sessions: int,
    calendar_days: int = SHADOW_MONTHLY_DAYS,
    unpaid_leaves: int = 0,
    db: Session | None = None,
    as_of: date | None = None,
) -> float:
    return predicted_amount_inr(
        case,
        share=therapist_share_inr(case, db=db, as_of=as_of),
        approved_sessions=approved_sessions,
        calendar_days=calendar_days,
        unpaid_leaves=unpaid_leaves,
    )


def predicted_client_amount_inr(
    case: Case,
    *,
    approved_sessions: int,
    calendar_days: int = SHADOW_MONTHLY_DAYS,
    unpaid_leaves: int = 0,
    db: Session | None = None,
    as_of: date | None = None,
) -> float:
    share = client_configured_share_inr(case)
    if db is not None and as_of is not None:
        from app.services import billing_rate_history_service

        share = billing_rate_history_service.resolve_client_amount_as_of(db, case, as_of)
    return predicted_amount_inr(
        case,
        share=share,
        approved_sessions=approved_sessions,
        calendar_days=calendar_days,
        unpaid_leaves=unpaid_leaves,
    )


@dataclass
class TherapistCaseSegment:
    """Therapist × case log window inside one billing month.

    ``first_log`` / ``last_log`` are MIN/MAX ``sessions.scheduled_date`` in this
    month joined to an approved daily log with ``transition_id IS NULL``.
    Not completed-clock, scheduled-without-log, or attendance.
    """

    therapist_user_id: int
    first_log: date | None
    last_log: date | None
    is_incoming_replacement: bool
    is_outgoing_replacement: bool


@dataclass
class CycleSegment:
    """One therapist's payout-report facts for a case × month."""

    therapist_user_id: int
    approved_sessions: int
    approved_absence: int
    hours: float
    calendar_days: int
    unpaid_leaves: int
    paid_leaves: int
    leave_credits: int
    transition_days: int
    transition_day_type: str
    transition_total: float
    therapist_start_date: date | None
    case_start_date: date | None
    case_end_date: date | None
    first_log: date | None
    last_log: date | None
    is_incoming_replacement: bool
    is_outgoing_replacement: bool
    # Frozen remun from CaseAssignment.billing_snapshot (outgoing / ended).
    locked_therapist_share_inr: float | None = None

    def _therapist_share(
        self, case: Case, *, db: Session | None = None, as_of: date | None = None
    ) -> float:
        if self.locked_therapist_share_inr is not None:
            return float(self.locked_therapist_share_inr)
        return therapist_share_inr(case, db=db, as_of=as_of)

    def therapist_subtotal(self, case: Case, *, db: Session | None = None, as_of: date | None = None) -> float:
        return predicted_amount_inr(
            case,
            share=self._therapist_share(case, db=db, as_of=as_of),
            approved_sessions=self.approved_sessions,
            calendar_days=self.calendar_days,
            unpaid_leaves=self.unpaid_leaves if uses_calendar_day_pay(case) else 0,
        )

    def therapist_gross(self, case: Case, *, db: Session | None = None, as_of: date | None = None) -> float:
        return round(self.therapist_subtotal(case, db=db, as_of=as_of) + self.transition_total, 2)

    def client_amount(self, case: Case, *, db: Session | None = None, as_of: date | None = None) -> float:
        return predicted_client_amount_inr(
            case,
            approved_sessions=self.approved_sessions,
            calendar_days=self.calendar_days,
            unpaid_leaves=self.unpaid_leaves if uses_calendar_day_pay(case) else 0,
            db=db,
            as_of=as_of,
        )



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
    # In-month first/last log: approved non-transition session scheduled_date only.
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
            DailyLog.transition_id.is_(None),
        )
        .group_by(TherapySession.therapist_user_id)
    ).all()

    therapist_ids = {int(r[0]) for r in log_rows}
    transition_therapist_ids = {
        int(value)
        for value in db.scalars(
            select(TherapySession.therapist_user_id)
            .join(DailyLog, DailyLog.session_id == TherapySession.id)
            .where(
                TherapySession.case_id == case_id,
                TherapySession.scheduled_date >= start,
                TherapySession.scheduled_date <= end,
                DailyLog.approval_status == LogApprovalStatus.APPROVED.value,
                DailyLog.transition_id.is_not(None),
            )
            .distinct()
        ).all()
    }
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

    for therapist_id in hour_only | (transition_therapist_ids - therapist_ids):
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


def _first_approved_normal_log_for_therapist(
    db: Session, case_id: int, therapist_user_id: int
) -> date | None:
    return db.scalar(
        select(func.min(TherapySession.scheduled_date))
        .join(DailyLog, DailyLog.session_id == TherapySession.id)
        .where(
            TherapySession.case_id == case_id,
            TherapySession.therapist_user_id == therapist_user_id,
            DailyLog.approval_status == LogApprovalStatus.APPROVED.value,
            DailyLog.transition_id.is_(None),
        )
    )


def _last_approved_log_for_therapist(
    db: Session, case_id: int, therapist_user_id: int
) -> date | None:
    """Latest approved non-transition log ``sessions.scheduled_date`` (all time).

    Same evidence type as in-month ``last_log``, not completed-clock or attendance.
    """
    return db.scalar(
        select(func.max(TherapySession.scheduled_date))
        .join(DailyLog, DailyLog.session_id == TherapySession.id)
        .where(
            TherapySession.case_id == case_id,
            TherapySession.therapist_user_id == therapist_user_id,
            DailyLog.approval_status == LogApprovalStatus.APPROVED.value,
            DailyLog.transition_id.is_(None),
        )
    )


def _transition_pay_for_therapist(
    db: Session,
    *,
    case_id: int,
    therapist_user_id: int,
    start: date,
    end: date,
) -> tuple[int, str, float]:
    rows = db.execute(
        select(
            CaseTherapistTransitionDay.id,
            CaseTherapistTransitionDay.day_type,
            CaseTherapistTransitionDay.pay_rate_inr,
        )
        .join(DailyLog, DailyLog.transition_day_id == CaseTherapistTransitionDay.id)
        .join(TherapySession, TherapySession.id == DailyLog.session_id)
        .where(
            TherapySession.case_id == case_id,
            TherapySession.therapist_user_id == therapist_user_id,
            TherapySession.scheduled_date >= start,
            TherapySession.scheduled_date <= end,
            DailyLog.approval_status == LogApprovalStatus.APPROVED.value,
        )
    ).all()
    unique_days = {
        int(day_id): (day_type, rate)
        for day_id, day_type, rate in rows
    }
    day_types = {str(day_type or "FULL_DAY") for day_type, _ in unique_days.values()}
    labels = {
        "HALF_DAY": "Half day",
        "FULL_DAY": "Full day",
    }
    day_type_label = ", ".join(sorted(labels.get(value, value.replace("_", " ").title()) for value in day_types))
    total = round(sum(float(rate or 0) for _, rate in unique_days.values()), 2)
    return len(unique_days), day_type_label, total


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
                DailyLog.transition_id.is_(None),
            )
        )
        or 0
    )


def _pending_sessions_for_therapist(
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
                DailyLog.approval_status == LogApprovalStatus.PENDING.value,
            )
        )
        or 0
    )


def _pending_absence_for_therapist(
    db: Session, case_id: int, therapist_user_id: int, start: date, end: date
) -> int:
    return int(
        db.scalar(
            select(func.count())
            .select_from(SessionAbsenceRequest)
            .join(TherapySession, SessionAbsenceRequest.session_id == TherapySession.id)
            .where(
                SessionAbsenceRequest.case_id == case_id,
                SessionAbsenceRequest.therapist_user_id == therapist_user_id,
                SessionAbsenceRequest.absence_type == SessionAbsenceType.CLIENT_ABSENT,
                SessionAbsenceRequest.status == SessionAbsenceStatus.PENDING_APPROVAL,
                TherapySession.scheduled_date >= start,
                TherapySession.scheduled_date <= end,
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


def build_cycle_segments(db: Session, case: Case, ym: str) -> list[CycleSegment]:
    """Payout-report segments for one case in a billing month (therapist × case)."""
    start, end = month_bounds(ym)
    year = int(ym.split("-")[0])
    segments: list[CycleSegment] = []
    for segment in _therapist_segments_for_case(db, case.id, start, end):
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
        transition_days, transition_day_type, transition_total = _transition_pay_for_therapist(
            db,
            case_id=case.id,
            therapist_user_id=segment.therapist_user_id,
            start=start,
            end=end,
        )
        if approved == 0 and hours <= 0 and transition_days == 0:
            continue
        assignment_start = _assignment_start_for_therapist(
            db,
            case.id,
            segment.therapist_user_id,
            month_start=start,
            month_end=end,
            reference_date=segment.first_log,
        )
        assignment = _assignment_for_month(
            db, case.id, segment.therapist_user_id, start, end
        )
        employment_start = _employment_start(db, segment.therapist_user_id)
        case_start = (
            _first_approved_normal_log_for_therapist(
                db, case.id, segment.therapist_user_id
            )
            if segment.is_incoming_replacement and transition_days
            else _first_session_ever_for_therapist(
                db, case.id, segment.therapist_user_id
            )
        )
        last_approved_ever = (
            _last_approved_log_for_therapist(
                db, case.id, segment.therapist_user_id
            )
            if segment.is_outgoing_replacement
            else None
        )
        segment_end = _resolve_segment_end(
            case=case,
            assignment=assignment,
            is_outgoing_replacement=segment.is_outgoing_replacement,
            last_log=segment.last_log,
            last_approved_ever=last_approved_ever,
            month_start=start,
            month_end=end,
        )
        calendar_days = calendar_days_for_segment(
            is_incoming_replacement=segment.is_incoming_replacement,
            is_outgoing_replacement=segment.is_outgoing_replacement,
            first_log=segment.first_log,
            last_log=segment.last_log,
            assignment_start=assignment_start,
            employment_start=employment_start,
            month_start=start,
            month_end=end,
            segment_end=segment_end,
        )
        if transition_days and (
            (segment.is_outgoing_replacement and segment.last_log is None)
            or (segment.is_incoming_replacement and segment.first_log is None)
        ):
            calendar_days = 0
        leave = _leave_for_case_row(db, therapist.id, case, ym)
        balance = leave_policy_service.get_leave_balance(db, therapist, year=year, as_of=end)
        leave_credits = int(
            balance.get("leave_credit_pending", balance.get("paid_remaining", 0)) or 0
        )
        locked_share: float | None = None
        if assignment is not None and isinstance(assignment.billing_snapshot, dict):
            locked = resolve_therapist_pay(assignment.billing_snapshot)
            if locked > 0:
                locked_share = locked
        segments.append(
            CycleSegment(
                therapist_user_id=segment.therapist_user_id,
                approved_sessions=approved,
                approved_absence=approved_absence,
                hours=hours,
                calendar_days=calendar_days,
                unpaid_leaves=int(leave.get("unpaid", 0)),
                paid_leaves=int(leave.get("paid", 0)),
                leave_credits=leave_credits,
                transition_days=transition_days,
                transition_day_type=transition_day_type,
                transition_total=transition_total,
                therapist_start_date=employment_start,
                case_start_date=case_start,
                case_end_date=segment_end,
                first_log=segment.first_log,
                last_log=segment.last_log,
                is_incoming_replacement=segment.is_incoming_replacement,
                is_outgoing_replacement=segment.is_outgoing_replacement,
                locked_therapist_share_inr=locked_share,
            )
        )
    return segments


def segment_for_therapist(
    db: Session, case: Case, therapist_user_id: int, ym: str
) -> CycleSegment | None:
    for segment in build_cycle_segments(db, case, ym):
        if segment.therapist_user_id == therapist_user_id:
            return segment
    return None


def therapist_case_gross_inr(db: Session, case: Case, ym: str) -> float:
    _ms, month_end = month_bounds(ym)
    return round(
        sum(
            s.therapist_gross(case, db=db, as_of=month_end)
            for s in build_cycle_segments(db, case, ym)
        ),
        2,
    )


def client_case_gross_inr(db: Session, case: Case, ym: str) -> float:
    """Family charge for the case-month: same days/sessions as payout, client allotment rates.

    Shadow/B2B uses ``calendar_days`` from ``build_cycle_segments``. Changing that
    day count moves receivables and payables together; Finance must sign both.
    """
    segments = build_cycle_segments(db, case, ym)
    _ms, month_end = month_bounds(ym)
    if not segments:
        return 0.0
    if case.billing_type == BillingType.MONTHLY_FIXED and not uses_calendar_day_pay(case):
        if any(s.approved_sessions > 0 for s in segments):
            from app.services import billing_rate_history_service

            return round(
                billing_rate_history_service.resolve_client_amount_as_of(db, case, month_end),
                2,
            )
        return 0.0
    return round(
        sum(s.client_amount(case, db=db, as_of=month_end) for s in segments),
        2,
    )


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
    transition_days: int,
    transition_day_type: str,
    transition_total: float,
    pending_sessions: int = 0,
    pending_absence: int = 0,
    leave_taken: int | None = None,
    parent_info: dict[str, Any] | None = None,
    db: Session | None = None,
) -> dict[str, Any]:
    _month_start, month_end = month_bounds(ym)
    share = therapist_share_inr(case, db=db, as_of=month_end)
    lumpsum = client_lumpsum_inr(case)
    per_sess = per_unit_from_share(case, share)
    unpaid = int(leave.get("unpaid", 0))
    subtotal = predicted_amount_inr(
        case,
        share=share,
        approved_sessions=approved_sessions,
        calendar_days=calendar_days,
        unpaid_leaves=unpaid if uses_calendar_day_pay(case) else 0,
    )
    leave_deduction = 0.0
    if uses_calendar_day_pay(case) and unpaid > 0:
        gross_before = predicted_amount_inr(
            case,
            share=share,
            approved_sessions=approved_sessions,
            calendar_days=calendar_days,
            unpaid_leaves=0,
        )
        leave_deduction = round(max(gross_before - subtotal, 0), 2)

    row: dict[str, Any] = {
        "caseId": case.id,
        "Month": month_long_label(ym),
        "Case ID": export_case_id(case),
        "Client Name": case_service.case_child_display_name(case) or "",
        "Parent Name": case_people_export_fields(
            case, parent_info=parent_info, include_therapist=False
        )["Parent Name"],
        "Therapist Name": user_display_name(therapist),
        "Therapist ID": export_therapist_id(therapist),
        "Service Type": case.service_type or case.product_module or "",
        "Therapist Start Date": therapist_start_date.isoformat() if therapist_start_date else "",
        "Case Start Date": case_start_date.isoformat() if case_start_date else "",
        "Case End Date": case_end_date.isoformat() if case_end_date else "",
        "Calendar Days": calendar_days,
        "Approved Sessions": approved_sessions,
        "Pending Sessions": pending_sessions,
        "Approved Absence": approved_absence,
        "Pending Absence": pending_absence,
        "Billable Absence": approved_absence,
        "Paid Leaves": int(leave.get("paid", 0)) if uses_calendar_day_pay(case) else "",
        "Unpaid Leaves": unpaid if uses_calendar_day_pay(case) else "",
        "Leave deduction": leave_deduction if uses_calendar_day_pay(case) else "",
        "Leave taken": leave_taken if not uses_calendar_day_pay(case) and leave_taken is not None else "",
        "Leave Credits": leave_credits,
        "Total Hours": round(hours, 2),
        "Billable Sessions": billable_sessions,
        "Billing Type": (
            case.billing_type.value if getattr(case.billing_type, "value", None) else (case.billing_type or "")
        ),
        # Aligned to case billing model: client charge + therapist lumpsum (no %).
        "Client Amount (INR)": lumpsum if lumpsum is not None else "",
        "Therapist Pay (INR)": round(share, 2) if share else "",
        "Therapist Unit Pay (INR)": per_sess if per_sess else "",
        "Predicted Subtotal": subtotal if subtotal else "",
        "Transition Days": transition_days,
        "Transition Day Type": transition_day_type,
        "Transition Days Total Amount": transition_total if transition_total else "",
        "Predicted Total": round(subtotal + transition_total, 2) if subtotal or transition_total else "",
    }
    return row


def payout_preview_rows(
    db: Session,
    ym: str,
    *,
    user: User | None = None,
    product_module: str | None = None,
) -> list[dict[str, Any]]:
    cases = scoped_cases(db, user, product_module=product_module, active_only=True)
    if not cases:
        return []

    parents = parent_by_child(db, {c.child_id for c in cases if c.child_id})
    rows: list[dict[str, Any]] = []
    start, end = month_bounds(ym)
    for case in cases[:MAX_EXPORT_ROWS]:
        for segment in build_cycle_segments(db, case, ym):
            therapist = db.get(User, segment.therapist_user_id)
            if not therapist:
                continue
            leave = {
                "paid": segment.paid_leaves,
                "unpaid": segment.unpaid_leaves,
                "carry_forward": 0,
            }
            billable = _billable_sessions_for_segment(
                case, segment.approved_sessions, segment.approved_absence
            )
            pending_sessions = _pending_sessions_for_therapist(
                db, case.id, segment.therapist_user_id, start, end
            )
            pending_absence = _pending_absence_for_therapist(
                db, case.id, segment.therapist_user_id, start, end
            )
            leave_taken = None
            if not uses_calendar_day_pay(case):
                case_leave = leave_days_in_month_for_case(db, therapist.id, case.id, ym)
                leave_taken = int(case_leave.get("paid", 0) or 0) + int(case_leave.get("unpaid", 0) or 0)
                if leave_taken == 0:
                    from app.models.leave import LeaveStatus, TherapistLeave

                    leaves = db.scalars(
                        select(TherapistLeave).where(
                            TherapistLeave.therapist_user_id == therapist.id,
                            TherapistLeave.status == LeaveStatus.APPROVED,
                            TherapistLeave.start_date <= end,
                            TherapistLeave.end_date >= start,
                        )
                    ).all()
                    from app.services.reports_export_helpers import leave_applies_to_case

                    leave_taken = sum(
                        (min(lv.end_date, end) - max(lv.start_date, start)).days + 1
                        for lv in leaves
                        if leave_applies_to_case(lv, case.id) or (not lv.case_id and not lv.case_ids)
                    )
            rows.append(
                payout_preview_row(
                    case,
                    ym=ym,
                    therapist=therapist,
                    approved_sessions=segment.approved_sessions,
                    approved_absence=segment.approved_absence,
                    billable_sessions=billable,
                    hours=segment.hours,
                    calendar_days=segment.calendar_days,
                    therapist_start_date=segment.therapist_start_date,
                    case_start_date=segment.case_start_date,
                    case_end_date=segment.case_end_date,
                    leave=leave,
                    leave_credits=segment.leave_credits,
                    transition_days=segment.transition_days,
                    transition_day_type=segment.transition_day_type,
                    transition_total=segment.transition_total,
                    pending_sessions=pending_sessions,
                    pending_absence=pending_absence,
                    leave_taken=leave_taken,
                    parent_info=parents.get(case.child_id) if case.child_id else None,
                    db=db,
                )
            )

    rows.sort(
        key=lambda r: (
            (r.get("Therapist Name") or "").lower(),
            r.get("Case ID") or "",
        )
    )
    return apply_therapist_total_column(rows)


def _predicted_total_inr(row: dict[str, Any]) -> float:
    raw = row.get("Predicted Total")
    if raw in (None, ""):
        return 0.0
    return float(raw)


def _therapist_group_key(row: dict[str, Any]) -> str:
    therapist_id = row.get("Therapist ID")
    if therapist_id not in (None, ""):
        return str(therapist_id)
    return (row.get("Therapist Name") or "").lower()


# Closed-month / pre-alignment snapshots — remap legacy headers on read.
_LEGACY_PAYOUT_PREVIEW_COLUMNS = {
    "Therapist Share": "Therapist Pay (INR)",
    "Per Session Share": "Therapist Unit Pay (INR)",
    "Per Session Pay (INR)": "Therapist Unit Pay (INR)",
    "Lumpsum Amount": "Client Amount (INR)",
}


def normalize_payout_preview_row(row: dict[str, Any]) -> dict[str, Any]:
    """Rename legacy percentage/package-era headers; drop duplicate legacy keys."""
    out: dict[str, Any] = {}
    for key, value in row.items():
        canon = _LEGACY_PAYOUT_PREVIEW_COLUMNS.get(key, key)
        if canon in out and key in _LEGACY_PAYOUT_PREVIEW_COLUMNS:
            # Prefer an already-canonical value over the legacy alias.
            continue
        out[canon] = value
    return out


def apply_therapist_total_column(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sum Predicted Total per therapist; show the total on the first row only."""
    if not rows:
        return rows

    normalized = [normalize_payout_preview_row(r) for r in rows]

    totals: dict[str, float] = {}
    for row in normalized:
        key = _therapist_group_key(row)
        totals[key] = round(totals.get(key, 0.0) + _predicted_total_inr(row), 2)

    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for row in normalized:
        new_row = {k: v for k, v in row.items() if k != "Therapist Total"}
        key = _therapist_group_key(row)
        if key not in seen:
            seen.add(key)
            total = totals[key]
            new_row["Therapist Total"] = total if total else ""
        else:
            new_row["Therapist Total"] = ""
        out.append(new_row)
    return out


# Demo seed populates May–July 2026. Those months are not a production merge gate.
DEMO_CALENDAR_SEED_MONTHS = frozenset({"2026-05", "2026-06", "2026-07"})

OUTGOING_CLAMP_CLASS_OUT_OF_MONTH = "out_of_month_end"
OUTGOING_CLAMP_CLASS_PRE_MONTH = "pre_month_closed"
OUTGOING_CLAMP_CLASS_CONTROL = "control"
OUTGOING_CLAMP_CLASS_UNBOUNDED = "unbounded_outgoing"

AFFECTED_OUTGOING_CLAMP_CLASSES = frozenset(
    {
        OUTGOING_CLAMP_CLASS_OUT_OF_MONTH,
        OUTGOING_CLAMP_CLASS_PRE_MONTH,
    }
)

_PAYOUT_CLAMP_PII_COLUMNS = frozenset(
    {
        "Client Name",
        "Parent Name",
        "Therapist Name",
        "Therapist Total",
    }
)

PAYOUT_CLAMP_MUTABLE_COLUMNS = frozenset(
    {
        "calendar_days",
        "therapist_gross_inr",
        "client_amount_inr",
        "Calendar Days",
        "Predicted Subtotal",
        "Predicted Total",
        "Leave deduction",
    }
)

CLIENT_GROSS_CLAMP_MUTABLE_COLUMNS = frozenset(
    {
        "client_gross_inr",
        "calendar_days",
    }
)


def is_demo_calendar_seed_month(ym: str) -> bool:
    return ym in DEMO_CALENDAR_SEED_MONTHS


def classify_outgoing_bound_end(
    bound_end: date | None, month_start: date, month_end: date
) -> str:
    if bound_end is None:
        return OUTGOING_CLAMP_CLASS_UNBOUNDED
    if bound_end < month_start:
        return OUTGOING_CLAMP_CLASS_PRE_MONTH
    if bound_end > month_end:
        return OUTGOING_CLAMP_CLASS_OUT_OF_MONTH
    return OUTGOING_CLAMP_CLASS_CONTROL


def classify_outgoing_calendar_day_segments(
    db: Session,
    ym: str,
    *,
    user: User | None = None,
) -> list[dict[str, Any]]:
    """ID-only audit of Shadow/B2B outgoing segments (no child/parent/therapist names)."""
    start, end = month_bounds(ym)
    rows: list[dict[str, Any]] = []
    for case in scoped_cases(db, user, active_only=False):
        if not uses_calendar_day_pay(case):
            continue
        for segment in build_cycle_segments(db, case, ym):
            if not segment.is_outgoing_replacement:
                continue
            bound = segment.case_end_date
            klass = classify_outgoing_bound_end(bound, start, end)
            unclamped_days = (
                calendar_days_outgoing(last_log=bound, segment_start_day=1)
                if bound is not None
                else None
            )
            therapist = db.get(User, segment.therapist_user_id)
            rows.append(
                {
                    "billing_month": ym,
                    "is_demo_seed_month": is_demo_calendar_seed_month(ym),
                    "case_id": case.id,
                    "case_code": case.case_code,
                    "therapist_user_id": segment.therapist_user_id,
                    "therapist_id": export_therapist_id(therapist),
                    "segment_start": (
                        segment.case_start_date.isoformat()
                        if segment.case_start_date
                        else None
                    ),
                    "segment_end": bound.isoformat() if bound else None,
                    "in_month_last_log": (
                        segment.last_log.isoformat() if segment.last_log else None
                    ),
                    "calendar_days": segment.calendar_days,
                    "unclamped_pay_month_day": unclamped_days,
                    "class": klass,
                }
            )
    rows.sort(
        key=lambda r: (
            r["case_id"],
            r["therapist_user_id"],
            r["segment_start"] or "",
        )
    )
    return rows


def freeze_outgoing_clamp_scope(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Affected outgoing segments: out-of-month end or closed before the pay month."""
    return [r for r in rows if r.get("class") in AFFECTED_OUTGOING_CLAMP_CLASSES]


def freeze_payout_identities(
    audit_rows: list[dict[str, Any]],
) -> set[tuple[str, str, str, str]]:
    return {payout_clamp_row_identity(r) for r in freeze_outgoing_clamp_scope(audit_rows)}


def normalize_payout_row_for_clamp_diff(row: dict[str, Any]) -> dict[str, Any]:
    """Drop PII and derived-position columns before Excel-preview replay compare."""
    canonical = normalize_payout_preview_row(row)
    return {k: v for k, v in canonical.items() if k not in _PAYOUT_CLAMP_PII_COLUMNS}


def payout_clamp_row_identity(row: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(row.get("case_id") or row.get("caseId") or ""),
        str(row.get("therapist_user_id") or row.get("Therapist ID") or ""),
        str(row.get("segment_start") or row.get("Case Start Date") or ""),
        str(row.get("segment_end") or row.get("Case End Date") or ""),
    )


def snapshot_calendar_day_money(
    db: Session,
    ym: str,
    *,
    user: User | None = None,
) -> dict[str, Any]:
    """Payout + client-gross snapshot for clamp replay (IDs and money, no PII names)."""
    _month_start, month_end = month_bounds(ym)
    payout_rows: list[dict[str, Any]] = []
    for case in scoped_cases(db, user, active_only=True):
        billing_type = getattr(case.billing_type, "value", case.billing_type)
        for segment in build_cycle_segments(db, case, ym):
            payout_rows.append(
                {
                    "case_id": case.id,
                    "case_code": case.case_code,
                    "therapist_user_id": segment.therapist_user_id,
                    "segment_start": (
                        segment.case_start_date.isoformat()
                        if segment.case_start_date
                        else ""
                    ),
                    "segment_end": (
                        segment.case_end_date.isoformat()
                        if segment.case_end_date
                        else ""
                    ),
                    "calendar_days": segment.calendar_days,
                    "approved_sessions": segment.approved_sessions,
                    "therapist_gross_inr": segment.therapist_gross(
                        case, db=db, as_of=month_end
                    ),
                    "client_amount_inr": segment.client_amount(
                        case, db=db, as_of=month_end
                    ),
                    "billing_type": str(billing_type or ""),
                    "uses_calendar_day_pay": uses_calendar_day_pay(case),
                }
            )
    payout_rows.sort(key=payout_clamp_row_identity)
    client_rows: list[dict[str, Any]] = []
    for case in scoped_cases(db, user, active_only=True):
        segments = build_cycle_segments(db, case, ym)
        billing_type = getattr(case.billing_type, "value", case.billing_type)
        client_rows.append(
            {
                "case_id": case.id,
                "case_code": case.case_code,
                "product_module": case.product_module or "",
                "billing_type": str(billing_type or ""),
                "uses_calendar_day_pay": uses_calendar_day_pay(case),
                "client_gross_inr": client_case_gross_inr(db, case, ym),
                "calendar_days": sum(s.calendar_days for s in segments),
                "approved_sessions": sum(s.approved_sessions for s in segments),
                "client_rate_per_session_inr": case.client_rate_per_session_inr,
                "package_amount_inr": case.package_amount_inr,
                "client_monthly_rate_inr": case.client_monthly_rate_inr,
            }
        )
    client_rows.sort(key=lambda r: (r["case_id"], r["case_code"] or ""))
    return {
        "billing_month": ym,
        "is_demo_seed_month": is_demo_calendar_seed_month(ym),
        "payout_rows": payout_rows,
        "client_rows": client_rows,
    }


def _values_differ(left: Any, right: Any) -> bool:
    if isinstance(left, float) or isinstance(right, float):
        try:
            return round(float(left or 0), 2) != round(float(right or 0), 2)
        except (TypeError, ValueError):
            return left != right
    return left != right


def diff_calendar_day_clamp_snapshots(
    before: dict[str, Any],
    after: dict[str, Any],
    *,
    frozen_identities: set[tuple[str, str, str, str]],
) -> dict[str, Any]:
    """Bounded replay gate: only frozen rows may change mutable money columns."""
    unexpected_payout: list[dict[str, Any]] = []
    payout_before = {payout_clamp_row_identity(r): r for r in before.get("payout_rows", [])}
    payout_after = {payout_clamp_row_identity(r): r for r in after.get("payout_rows", [])}
    if set(payout_before) != set(payout_after):
        unexpected_payout.append(
            {
                "reason": "payout_row_set_changed",
                "added": sorted(set(payout_after) - set(payout_before)),
                "removed": sorted(set(payout_before) - set(payout_after)),
            }
        )
    for key in sorted(set(payout_before) & set(payout_after)):
        left, right = payout_before[key], payout_after[key]
        changed = [
            col
            for col in set(left) | set(right)
            if _values_differ(left.get(col), right.get(col))
        ]
        if not changed:
            continue
        unexpected_cols = [c for c in changed if c not in PAYOUT_CLAMP_MUTABLE_COLUMNS]
        if unexpected_cols or key not in frozen_identities:
            unexpected_payout.append(
                {
                    "identity": key,
                    "changed": changed,
                    "unexpected_columns": unexpected_cols,
                    "in_frozen_scope": key in frozen_identities,
                }
            )

    unexpected_client: list[dict[str, Any]] = []
    client_before = {int(r["case_id"]): r for r in before.get("client_rows", [])}
    client_after = {int(r["case_id"]): r for r in after.get("client_rows", [])}
    if set(client_before) != set(client_after):
        unexpected_client.append(
            {
                "reason": "client_row_set_changed",
                "added": sorted(set(client_after) - set(client_before)),
                "removed": sorted(set(client_before) - set(client_after)),
            }
        )
    frozen_case_ids = {
        int(case_id) for case_id, *_rest in frozen_identities if str(case_id).isdigit()
    }
    for case_id in sorted(set(client_before) & set(client_after)):
        left, right = client_before[case_id], client_after[case_id]
        changed = [
            col
            for col in set(left) | set(right)
            if _values_differ(left.get(col), right.get(col))
        ]
        if not changed:
            continue
        calendar_day = bool(left.get("uses_calendar_day_pay"))
        allowed = CLIENT_GROSS_CLAMP_MUTABLE_COLUMNS if calendar_day else frozenset()
        unexpected_cols = [c for c in changed if c not in allowed]
        if unexpected_cols or (calendar_day and case_id not in frozen_case_ids):
            unexpected_client.append(
                {
                    "case_id": case_id,
                    "changed": changed,
                    "unexpected_columns": unexpected_cols,
                    "in_frozen_scope": case_id in frozen_case_ids,
                }
            )

    return {
        "ok": not unexpected_payout and not unexpected_client,
        "unexpected_payout": unexpected_payout,
        "unexpected_client": unexpected_client,
    }
