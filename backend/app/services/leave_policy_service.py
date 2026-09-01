"""Monthly leave credit accrual, consumption, and paid/unpaid split suggestions."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.case import Case
from app.models.leave import LeaveBillingCategory, LeaveStatus, LeaveType, TherapistLeave
from app.models.therapist_profile import TherapistProfile
from app.models.user import User
from app.services import leave_service
from app.services.leave_bulk_import_service import get_year_snapshot

SHADOW_SERVICE_LINE = "shadow_support"


@dataclass
class LeaveSplitSuggestion:
    paid_days: int
    unpaid_days: int
    total_days: int
    has_shadow_cases: bool
    message: str

    @property
    def carry_forward_days(self) -> int:
        """Legacy alias — carry forward is not used in v2 policy."""
        return 0


def is_staff_leave_user(user: User) -> bool:
    """Legacy helper — monthly credit policy applies to all therapists equally."""
    return False


def _months_in_range(start: date, end: date) -> int:
    if end < start:
        return 0
    return (end.year - start.year) * 12 + (end.month - start.month) + 1


def credits_earned_in_year(
    employment_start: date | None,
    year: int,
    *,
    as_of: date | None = None,
) -> int:
    """One credit per calendar month from join month through as_of (within year)."""
    if not employment_start:
        return 0
    year_start = date(year, 1, 1)
    year_end = date(year, 12, 31)
    if employment_start > year_end:
        return 0
    period_start = max(employment_start, year_start)
    period_end = min(as_of or date.today(), year_end)
    return _months_in_range(period_start, period_end)


def _leave_case_ids(leave: TherapistLeave) -> list[int]:
    if leave.case_ids:
        return [int(x) for x in leave.case_ids if x is not None]
    if leave.case_id is not None:
        return [int(leave.case_id)]
    return []


def _leave_includes_shadow(db: Session, leave: TherapistLeave) -> bool:
    if leave.includes_shadow_cases:
        return True
    if leave.service_line == SHADOW_SERVICE_LINE:
        return True
    for cid in _leave_case_ids(leave):
        case = db.get(Case, cid)
        if case and (case.product_module or "").strip().lower() == SHADOW_SERVICE_LINE:
            return True
    return False


def _paid_unpaid_for_leave(db: Session, leave: TherapistLeave, year: int) -> tuple[int, int]:
    """Paid/unpaid day counts for a leave row within a calendar year."""
    if leave.status != LeaveStatus.APPROVED:
        return 0, 0
    days = leave_service.days_in_calendar_year(leave, year)
    if days <= 0:
        return 0, 0

    if leave.paid_days is not None or leave.unpaid_days is not None:
        total = leave_service.leave_day_count(leave.start_date, leave.end_date)
        if total <= 0:
            return 0, 0
        paid = int(leave.paid_days or 0)
        unpaid = int(leave.unpaid_days or 0)
        if paid + unpaid != total and total > 0:
            ratio_paid = paid / total
            paid = round(days * ratio_paid)
            unpaid = max(days - paid, 0)
        else:
            paid = min(paid, days)
            unpaid = min(unpaid, max(days - paid, 0))
        if not _leave_includes_shadow(db, leave):
            return 0, days
        return paid, unpaid

    includes_shadow = _leave_includes_shadow(db, leave)
    cat = leave.billing_category
    if cat is None:
        cat = LeaveBillingCategory.UNPAID if leave.leave_type == LeaveType.UNPAID else LeaveBillingCategory.PAID
    if not includes_shadow:
        return 0, days
    if cat in (LeaveBillingCategory.PAID, LeaveBillingCategory.CARRY_FORWARD):
        return days, 0
    return 0, days


@dataclass
class ConsumptionDetail:
    """Paid/unpaid consumption for a therapist within a year, with unpaid cause split."""

    paid: int
    unpaid_total: int
    unpaid_homecare: int
    unpaid_over_limit: int


def computed_consumption_detail(
    db: Session, therapist_user_id: int, year: int, *, as_of: date | None = None
) -> ConsumptionDetail:
    """Allocate credits chronologically and split unpaid days by cause.

    Unpaid days fall into two buckets:
    - ``unpaid_homecare``: leave on non-shadow cases, which never uses credits.
    - ``unpaid_over_limit``: shadow days that could not be covered because the
      year's leave credits were exhausted.
    """
    profile = db.scalars(
        select(TherapistProfile).where(TherapistProfile.user_id == therapist_user_id)
    ).first()
    employment_start = profile.employment_start_date if profile else None
    today = as_of or date.today()
    if year < today.year:
        accrual_as_of = date(year, 12, 31)
    elif year > today.year:
        accrual_as_of = date(year, 1, 1)
    else:
        accrual_as_of = today
    credits_pool = credits_earned_in_year(employment_start, year, as_of=accrual_as_of)

    leaves = db.scalars(
        select(TherapistLeave).where(
            TherapistLeave.therapist_user_id == therapist_user_id,
            TherapistLeave.status == LeaveStatus.APPROVED,
        )
    ).all()
    year_leaves = [lv for lv in leaves if leave_service.leave_overlaps_year(lv, year)]
    year_leaves.sort(key=lambda lv: (lv.start_date, lv.id))

    paid = unpaid_homecare = unpaid_over_limit = 0
    credits_left = credits_pool
    for lv in year_leaves:
        includes_shadow = _leave_includes_shadow(db, lv)
        if lv.paid_days is not None and lv.unpaid_days is not None:
            p, u = _paid_unpaid_for_leave(db, lv, year)
            paid += p
            if includes_shadow:
                unpaid_over_limit += u
            else:
                unpaid_homecare += u
            credits_left = max(credits_left - p, 0)
            continue

        days = leave_service.days_in_calendar_year(lv, year)
        if days <= 0:
            continue
        if not includes_shadow:
            unpaid_homecare += days
            continue
        if credits_left > 0:
            p = min(days, credits_left)
            u = days - p
            credits_left -= p
        else:
            p = 0
            u = days
        paid += p
        unpaid_over_limit += u

    return ConsumptionDetail(
        paid=paid,
        unpaid_total=unpaid_homecare + unpaid_over_limit,
        unpaid_homecare=unpaid_homecare,
        unpaid_over_limit=unpaid_over_limit,
    )


def computed_consumption(
    db: Session, therapist_user_id: int, year: int
) -> tuple[int, int, int]:
    """Returns (paid_days, carry_forward_days_legacy, unpaid_days) using credit allocation order."""
    detail = computed_consumption_detail(db, therapist_user_id, year)
    return detail.paid, 0, detail.unpaid_total


def get_leave_balance(
    db: Session,
    user: User,
    *,
    year: int | None = None,
    profile: TherapistProfile | None = None,
    as_of: date | None = None,
) -> dict:
    year = year or date.today().year
    if profile is None:
        profile = db.scalars(
            select(TherapistProfile).where(TherapistProfile.user_id == user.id)
        ).first()

    employment_start = profile.employment_start_date if profile else None
    today = as_of or date.today()
    if year > today.year:
        credits_earned = 0
    elif year < today.year:
        credits_earned = credits_earned_in_year(employment_start, year, as_of=date(year, 12, 31))
    else:
        credits_earned = credits_earned_in_year(employment_start, year, as_of=today)

    snapshot = get_year_snapshot(profile, year)
    if snapshot is not None:
        paid_used = int(snapshot.get("paid_used") or 0)
        unpaid_homecare = int(snapshot.get("unpaid_homecare") or 0)
        unpaid_over_limit = int(snapshot.get("unpaid_over_limit") or 0)
        unpaid_used = unpaid_homecare + unpaid_over_limit
        credits_remaining = max(credits_earned - paid_used, 0)
        usage_snapshot_applied = True
    else:
        detail = computed_consumption_detail(db, user.id, year, as_of=as_of)
        paid_used = detail.paid
        unpaid_used = detail.unpaid_total
        unpaid_homecare = detail.unpaid_homecare
        unpaid_over_limit = detail.unpaid_over_limit
        credits_remaining = max(credits_earned - paid_used, 0)
        usage_snapshot_applied = False

    return {
        "year": year,
        "leave_credit_pending": credits_remaining,
        "credits_earned": credits_earned,
        "paid_leaves_taken": paid_used,
        "unpaid_leaves_taken": unpaid_used,
        "unpaid_homecare": unpaid_homecare,
        "unpaid_over_limit": unpaid_over_limit,
        "usage_snapshot_applied": usage_snapshot_applied,
        "employment_start_date": employment_start.isoformat() if employment_start else None,
        "profile_status": profile.status.value if profile else None,
        "requires_employment_start_date": not employment_start,
        "balance_updated": employment_start is not None,
        # Legacy aliases for gradual UI migration
        "entitlement_paid": credits_earned,
        "paid_remaining": credits_remaining,
        "paid_used_effective": paid_used,
        "computed_paid_used": paid_used,
        "computed_unpaid_days": unpaid_used,
        "computed_carry_forward_used": 0,
        "carry_forward_used_display": 0,
        "backfill_paid_used": 0,
        "backfill_carry_forward_used": 0,
        "backfill_note": None,
        "policy_tier": "monthly_credit",
    }


def is_leave_balance_updated(user: User, profile: TherapistProfile | None, year: int) -> bool:
    if not profile or not profile.employment_start_date:
        return False
    return True


def resolve_case_context(
    db: Session, therapist_user_id: int, case_ids: list[int]
) -> tuple[list[Case], bool, bool]:
    from app.core.permissions import get_active_assignment

    if not case_ids:
        return [], False, False
    cases: list[Case] = []
    has_shadow = False
    has_homecare = False
    for cid in case_ids:
        case = db.get(Case, cid)
        if not case:
            raise ValueError(f"Case {cid} not found")
        if not get_active_assignment(db, cid, therapist_user_id):
            raise ValueError(f"Therapist is not assigned to case {case.case_code or cid}")
        cases.append(case)
        mod = (case.product_module or "homecare").strip().lower()
        if mod == SHADOW_SERVICE_LINE:
            has_shadow = True
        else:
            has_homecare = True
    return cases, has_shadow, has_homecare


def compute_leave_split(
    db: Session,
    user: User,
    *,
    start_date: date,
    end_date: date,
    case_ids: list[int] | None = None,
    year: int | None = None,
) -> LeaveSplitSuggestion:
    year = year or start_date.year
    total = leave_service.leave_day_count(start_date, end_date)
    profile = db.scalars(select(TherapistProfile).where(TherapistProfile.user_id == user.id)).first()
    balance = get_leave_balance(db, user, year=year, profile=profile)

    has_shadow = False
    if case_ids:
        _, has_shadow, _ = resolve_case_context(db, user.id, case_ids)

    if not has_shadow:
        return LeaveSplitSuggestion(
            paid_days=0,
            unpaid_days=total,
            total_days=total,
            has_shadow_cases=False,
            message="Homecare-only — sessions will be cancelled; no leave credits used.",
        )

    remaining = balance["leave_credit_pending"]
    paid = min(total, remaining)
    unpaid = max(total - paid, 0)
    if paid and unpaid:
        msg = f"{paid} paid leave + {unpaid} unpaid leave"
    elif paid:
        msg = f"{paid} paid leave day{'s' if paid != 1 else ''}"
    else:
        msg = f"{total} unpaid leave day{'s' if total != 1 else ''} — no credits remaining"
    return LeaveSplitSuggestion(
        paid_days=paid,
        unpaid_days=unpaid,
        total_days=total,
        has_shadow_cases=True,
        message=msg,
    )


def suggest_leave_split(
    db: Session,
    user: User,
    *,
    start_date: date,
    end_date: date,
    service_line: str,
    case_ids: list[int] | None = None,
    year: int | None = None,
) -> LeaveSplitSuggestion:
    if not case_ids:
        total = leave_service.leave_day_count(start_date, end_date)
        if service_line.strip().lower() != SHADOW_SERVICE_LINE:
            return LeaveSplitSuggestion(
                paid_days=0,
                unpaid_days=total,
                total_days=total,
                has_shadow_cases=False,
                message="No shadow cases — leave will not use credits.",
            )
        profile = db.scalars(select(TherapistProfile).where(TherapistProfile.user_id == user.id)).first()
        balance = get_leave_balance(db, user, year=year or start_date.year, profile=profile)
        remaining = balance["leave_credit_pending"]
        paid = min(total, remaining)
        unpaid = max(total - paid, 0)
        if paid and unpaid:
            msg = f"{paid} paid leave + {unpaid} unpaid leave"
        elif paid:
            msg = f"{paid} paid leave day{'s' if paid != 1 else ''}"
        else:
            msg = f"{total} unpaid leave day{'s' if total != 1 else ''} — no credits remaining"
        return LeaveSplitSuggestion(
            paid_days=paid,
            unpaid_days=unpaid,
            total_days=total,
            has_shadow_cases=True,
            message=msg,
        )
    return compute_leave_split(
        db, user, start_date=start_date, end_date=end_date, case_ids=case_ids, year=year
    )


def resolve_billing_category(
    db: Session,
    user: User,
    *,
    start_date: date,
    end_date: date,
    service_line: str,
    case_ids: list[int] | None,
    requested_category: LeaveBillingCategory | None,
) -> tuple[LeaveBillingCategory, int, int, bool]:
    split = suggest_leave_split(
        db,
        user,
        start_date=start_date,
        end_date=end_date,
        service_line=service_line,
        case_ids=case_ids,
    )
    # Therapists may voluntarily choose unpaid even when credits remain (bill what they submit).
    if requested_category == LeaveBillingCategory.UNPAID:
        return LeaveBillingCategory.UNPAID, 0, split.total_days, split.has_shadow_cases
    # No paid balance → unpaid automatically.
    if split.paid_days <= 0:
        return LeaveBillingCategory.UNPAID, split.paid_days, split.unpaid_days, split.has_shadow_cases
    if split.unpaid_days > 0:
        return LeaveBillingCategory.PAID, split.paid_days, split.unpaid_days, split.has_shadow_cases
    return LeaveBillingCategory.PAID, split.paid_days, split.unpaid_days, split.has_shadow_cases


def map_leave_type_from_billing(cat: LeaveBillingCategory) -> LeaveType:
    if cat == LeaveBillingCategory.UNPAID:
        return LeaveType.UNPAID
    return LeaveType.ANNUAL


def primary_service_line(has_shadow: bool, has_homecare: bool) -> str:
    if has_shadow and has_homecare:
        return "mixed"
    if has_shadow:
        return SHADOW_SERVICE_LINE
    return "homecare"
