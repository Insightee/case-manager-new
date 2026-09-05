"""Monthly leave credit accrual, consumption, and paid/unpaid split suggestions."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.case import Case
from app.models.leave import LeaveBillingCategory, LeaveStatus, LeaveType, TherapistLeave
from app.models.therapist_profile import TherapistProfile
from app.models.user import User
from app.services import leave_dates_service as leave_dates
from app.services import leave_service
from app.services.leave_bulk_import_service import get_year_snapshot

SHADOW_SERVICE_LINE = "shadow_support"


@dataclass(frozen=True)
class LeaveDayAllocation:
    day: date
    status: str

    def to_dict(self) -> dict:
        return {"date": self.day.isoformat(), "status": self.status}


def iter_leave_dates(start: date, end: date) -> list[date]:
    if end < start:
        return []
    out: list[date] = []
    cursor = start
    while cursor <= end:
        out.append(cursor)
        cursor += timedelta(days=1)
    return out


def allocate_leave_days(
    start: date | None = None,
    end: date | None = None,
    *,
    paid_days: int,
    unpaid_days: int,
    dates: list[date] | None = None,
) -> list[LeaveDayAllocation]:
    """Assign paid credits to the earliest days; leftover days are unpaid."""
    days = list(dates) if dates is not None else iter_leave_dates(start, end)
    total = len(days)
    if total <= 0:
        return []
    paid = max(int(paid_days or 0), 0)
    unpaid = max(int(unpaid_days or 0), 0)
    if paid + unpaid != total:
        paid = min(paid, total)
        unpaid = total - paid
    return [
        LeaveDayAllocation(day=day, status="paid" if idx < paid else "unpaid")
        for idx, day in enumerate(days)
    ]


def format_day_split_message(
    allocations: list[LeaveDayAllocation],
    *,
    has_shadow_cases: bool,
) -> str:
    paid = [a.day for a in allocations if a.status == "paid"]
    unpaid = [a.day for a in allocations if a.status == "unpaid"]

    def _fmt(days: list[date]) -> str:
        return ", ".join(d.strftime("%d %b") for d in days)

    if not has_shadow_cases:
        return "Homecare-only — sessions will be cancelled; no leave credits used."
    if paid and unpaid:
        unpaid_word = "day" if len(unpaid) == 1 else "days"
        return (
            f"{_fmt(paid)} paid. {_fmt(unpaid)} unpaid — "
            f"you will not be paid for the unpaid {unpaid_word}."
        )
    if paid:
        return f"{_fmt(paid)} paid leave"
    if unpaid:
        unpaid_word = "this day" if len(unpaid) == 1 else "these days"
        return f"{_fmt(unpaid)} unpaid — you will not be paid for {unpaid_word}."
    return ""


def paid_unpaid_totals_for_leave(db: Session, leave: TherapistLeave) -> tuple[int, int]:
    includes_shadow = _leave_includes_shadow(db, leave)
    if includes_shadow:
        total = len(leave_dates.billable_leave_dates(db, leave, shadow_only=True))
    else:
        total = leave_service.leave_day_count(leave.start_date, leave.end_date)
    if total <= 0:
        return 0, 0
    if leave.paid_days is not None or leave.unpaid_days is not None:
        paid = max(int(leave.paid_days or 0), 0)
        unpaid = max(int(leave.unpaid_days or 0), 0)
        if paid + unpaid != total:
            paid = min(paid, total)
            unpaid = total - paid
        return paid, unpaid
    if not includes_shadow:
        return 0, total
    cat = leave.billing_category
    if cat is None:
        cat = LeaveBillingCategory.UNPAID if leave.leave_type == LeaveType.UNPAID else LeaveBillingCategory.PAID
    if cat in (LeaveBillingCategory.PAID, LeaveBillingCategory.CARRY_FORWARD):
        return total, 0
    return 0, total


def allocations_for_leave(db: Session, leave: TherapistLeave) -> list[LeaveDayAllocation]:
    paid, unpaid = paid_unpaid_totals_for_leave(db, leave)
    includes_shadow = _leave_includes_shadow(db, leave)
    dates = (
        leave_dates.billable_leave_dates(db, leave, shadow_only=True)
        if includes_shadow
        else iter_leave_dates(leave.start_date, leave.end_date)
    )
    return allocate_leave_days(
        leave.start_date,
        leave.end_date,
        paid_days=paid,
        unpaid_days=unpaid,
        dates=dates,
    )


def month_paid_unpaid_from_allocations(
    allocations: list[LeaveDayAllocation],
    start: date,
    end: date,
) -> tuple[int, int]:
    paid = unpaid = 0
    for item in allocations:
        if start <= item.day <= end:
            if item.status == "paid":
                paid += 1
            else:
                unpaid += 1
    return paid, unpaid


@dataclass
class LeaveSplitSuggestion:
    paid_days: int
    unpaid_days: int
    total_days: int
    has_shadow_cases: bool
    message: str
    day_allocations: list[dict] = field(default_factory=list)

    @property
    def carry_forward_days(self) -> int:
        """Legacy alias — carry forward is not used in v2 policy."""
        return 0


def _split_suggestion(
    *,
    start: date,
    end: date,
    paid_days: int,
    unpaid_days: int,
    has_shadow_cases: bool,
    message: str | None = None,
    dates: list[date] | None = None,
) -> LeaveSplitSuggestion:
    allocations = allocate_leave_days(
        start, end, paid_days=paid_days, unpaid_days=unpaid_days, dates=dates
    )
    return LeaveSplitSuggestion(
        paid_days=paid_days,
        unpaid_days=unpaid_days,
        total_days=paid_days + unpaid_days,
        has_shadow_cases=has_shadow_cases,
        message=message or format_day_split_message(allocations, has_shadow_cases=has_shadow_cases),
        day_allocations=[item.to_dict() for item in allocations],
    )


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
    year_start = date(year, 1, 1)
    year_end = date(year, 12, 31)
    return month_paid_unpaid_from_allocations(
        allocations_for_leave(db, leave),
        year_start,
        year_end,
    )


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

        days = leave_service.days_in_calendar_year(
            lv, year, db, shadow_only=includes_shadow
        )
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
    profile = db.scalars(select(TherapistProfile).where(TherapistProfile.user_id == user.id)).first()
    balance = get_leave_balance(db, user, year=year, profile=profile)

    has_shadow = False
    cases: list[Case] = []
    if case_ids:
        cases, has_shadow, _ = resolve_case_context(db, user.id, case_ids)

    if not has_shadow:
        total = leave_service.leave_day_count(start_date, end_date)
        return _split_suggestion(
            start=start_date,
            end=end_date,
            paid_days=0,
            unpaid_days=total,
            has_shadow_cases=False,
            message="Homecare-only — sessions will be cancelled; no leave credits used.",
        )

    shadow_ids = [
        c.id for c in cases if (c.product_module or "").strip().lower() == SHADOW_SERVICE_LINE
    ]
    scheduled = leave_dates.scheduled_dates_in_range(
        db,
        therapist_user_id=user.id,
        start=start_date,
        end=end_date,
        case_ids=shadow_ids or case_ids,
        shadow_only=True,
    )
    total = len(scheduled)
    remaining = balance["leave_credit_pending"]
    paid = min(total, remaining)
    unpaid = max(total - paid, 0)
    return _split_suggestion(
        start=start_date,
        end=end_date,
        paid_days=paid,
        unpaid_days=unpaid,
        has_shadow_cases=True,
        dates=scheduled,
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
        if service_line.strip().lower() != SHADOW_SERVICE_LINE:
            total = leave_service.leave_day_count(start_date, end_date)
            return _split_suggestion(
                start=start_date,
                end=end_date,
                paid_days=0,
                unpaid_days=total,
                has_shadow_cases=False,
                message="No shadow cases — leave will not use credits.",
            )
        scheduled = leave_dates.scheduled_dates_in_range(
            db,
            therapist_user_id=user.id,
            start=start_date,
            end=end_date,
            case_ids=None,
            shadow_only=True,
        )
        total = len(scheduled)
        profile = db.scalars(select(TherapistProfile).where(TherapistProfile.user_id == user.id)).first()
        balance = get_leave_balance(db, user, year=year or start_date.year, profile=profile)
        remaining = balance["leave_credit_pending"]
        paid = min(total, remaining)
        unpaid = max(total - paid, 0)
        return _split_suggestion(
            start=start_date,
            end=end_date,
            paid_days=paid,
            unpaid_days=unpaid,
            has_shadow_cases=True,
            dates=scheduled,
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


def apply_live_paid_unpaid(db: Session, leave: TherapistLeave, user: User) -> TherapistLeave:
    """Recompute paid/unpaid from live remaining credits (call on approve)."""
    requested = leave.billing_category if leave.billing_category == LeaveBillingCategory.UNPAID else None
    billing, paid_days, unpaid_days, includes_shadow = resolve_billing_category(
        db,
        user,
        start_date=leave.start_date,
        end_date=leave.end_date,
        service_line=(leave.service_line or SHADOW_SERVICE_LINE),
        case_ids=_leave_case_ids(leave) or None,
        requested_category=requested,
    )
    leave.billing_category = billing
    leave.paid_days = paid_days
    leave.unpaid_days = unpaid_days
    leave.includes_shadow_cases = includes_shadow
    return leave


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
