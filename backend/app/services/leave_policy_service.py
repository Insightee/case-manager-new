"""Leave entitlement, consumption, and split suggestions."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.permissions import RoleName
from app.models.leave import LeaveBillingCategory, LeaveStatus, LeaveType, TherapistLeave
from app.models.therapist_profile import TherapistProfile
from app.models.user import User
from app.services import leave_service

SHADOW_SERVICE_LINE = "shadow_support"
STAFF_LEAVE_ROLES = frozenset(
    {RoleName.ADMIN.value, RoleName.CASE_MANAGER.value, RoleName.SUPER_ADMIN.value}
)


@dataclass
class LeaveSplitSuggestion:
    paid_days: int
    carry_forward_days: int
    unpaid_days: int
    total_days: int
    message: str


def is_staff_leave_user(user: User) -> bool:
    return bool(STAFF_LEAVE_ROLES.intersection(user.role_names))


def _months_worked_in_year(employment_start: date, year: int) -> int:
    year_start = date(year, 1, 1)
    year_end = date(year, 12, 31)
    start = max(employment_start, year_start)
    if start > year_end:
        return 0
    return (year_end.year - start.year) * 12 + (year_end.month - start.month) + 1


def get_entitlement_paid(user: User, profile: TherapistProfile | None, year: int) -> int:
    if is_staff_leave_user(user):
        return 20
    if not profile or not profile.employment_start_date:
        return 0
    start = profile.employment_start_date
    today = date.today()
    tenure_days = (today - start).days
    if tenure_days >= 365:
        return 12
    return _months_worked_in_year(start, year)


def _backfill_adjustments(profile: TherapistProfile | None, year: int) -> tuple[int, int, Optional[str]]:
    if not profile or profile.leave_balance_year != year:
        return 0, 0, None
    return (
        int(profile.leave_paid_days_backfill or 0),
        int(profile.leave_carry_forward_days_backfill or 0),
        profile.leave_backfill_note,
    )


def is_leave_balance_updated(
    user: User, profile: TherapistProfile | None, year: int
) -> bool:
    """True when HR has configured leave balance for this calendar year (or user is internal staff)."""
    if is_staff_leave_user(user):
        return True
    if not profile:
        return False
    if profile.leave_balance_year != year:
        return False
    if not profile.employment_start_date:
        return False
    return profile.leave_backfill_updated_at is not None


def _days_for_leave_in_year(leave: TherapistLeave, year: int) -> int:
    return leave_service.days_in_calendar_year(leave, year)


def computed_consumption(
    db: Session, therapist_user_id: int, year: int
) -> tuple[int, int, int]:
    """Returns (paid_days, carry_forward_days, unpaid_days) from approved leaves."""
    leaves = db.scalars(
        select(TherapistLeave).where(
            TherapistLeave.therapist_user_id == therapist_user_id,
            TherapistLeave.status == LeaveStatus.APPROVED,
        )
    ).all()
    paid = carry = unpaid = 0
    for lv in leaves:
        days = _days_for_leave_in_year(lv, year)
        if days <= 0:
            continue
        cat = lv.billing_category
        if cat is None:
            if lv.leave_type == LeaveType.UNPAID:
                cat = LeaveBillingCategory.UNPAID
            else:
                cat = LeaveBillingCategory.PAID
        if cat == LeaveBillingCategory.PAID:
            paid += days
        elif cat == LeaveBillingCategory.CARRY_FORWARD:
            carry += days
        else:
            unpaid += days
    return paid, carry, unpaid


def get_leave_balance(
    db: Session,
    user: User,
    *,
    year: int | None = None,
    profile: TherapistProfile | None = None,
) -> dict:
    year = year or date.today().year
    if profile is None:
        profile = db.scalars(
            select(TherapistProfile).where(TherapistProfile.user_id == user.id)
        ).first()

    entitlement = get_entitlement_paid(user, profile, year)
    computed_paid, computed_carry, computed_unpaid = computed_consumption(db, user.id, year)
    backfill_paid, backfill_carry, backfill_note = _backfill_adjustments(profile, year)

    paid_effective = computed_paid + backfill_paid
    paid_remaining = max(entitlement - paid_effective, 0)

    return {
        "year": year,
        "entitlement_paid": entitlement,
        "computed_paid_used": computed_paid,
        "computed_carry_forward_used": computed_carry,
        "computed_unpaid_days": computed_unpaid,
        "backfill_paid_used": backfill_paid,
        "backfill_carry_forward_used": backfill_carry,
        "paid_used_effective": paid_effective,
        "paid_remaining": paid_remaining,
        "carry_forward_used_display": computed_carry + backfill_carry,
        "employment_start_date": profile.employment_start_date.isoformat()
        if profile and profile.employment_start_date
        else None,
        "backfill_note": backfill_note,
        "policy_tier": "staff_20" if is_staff_leave_user(user) else ("annual_12" if profile and profile.employment_start_date and (date.today() - profile.employment_start_date).days >= 365 else "monthly_pro_rata"),
        "requires_employment_start_date": not is_staff_leave_user(user)
        and not (profile and profile.employment_start_date),
        "balance_updated": is_leave_balance_updated(user, profile, year),
    }


def suggest_leave_split(
    db: Session,
    user: User,
    *,
    start_date: date,
    end_date: date,
    service_line: str,
    year: int | None = None,
) -> LeaveSplitSuggestion:
    year = year or start_date.year
    total = leave_service.leave_day_count(start_date, end_date)
    profile = db.scalars(select(TherapistProfile).where(TherapistProfile.user_id == user.id)).first()
    balance = get_leave_balance(db, user, year=year, profile=profile)
    remaining = balance["paid_remaining"]

    if service_line != SHADOW_SERVICE_LINE:
        return LeaveSplitSuggestion(
            paid_days=0,
            carry_forward_days=0,
            unpaid_days=total,
            total_days=total,
            message="No paid leaves for this service line — all days marked unpaid.",
        )

    if remaining <= 0:
        carry = min(total, total)
        return LeaveSplitSuggestion(
            paid_days=0,
            carry_forward_days=total,
            unpaid_days=0,
            total_days=total,
            message="No paid balance remaining this year — days marked carry forward.",
        )

    paid = min(1, total, remaining)
    carry = max(total - paid, 0)
    return LeaveSplitSuggestion(
        paid_days=paid,
        carry_forward_days=carry,
        unpaid_days=0,
        total_days=total,
        message=f"Suggested: {paid} paid, {carry} carry forward (shadow monthly rule).",
    )


def resolve_billing_category(
    db: Session,
    user: User,
    *,
    start_date: date,
    end_date: date,
    service_line: str,
    requested_category: LeaveBillingCategory | None,
) -> LeaveBillingCategory:
    suggestion = suggest_leave_split(
        db, user, start_date=start_date, end_date=end_date, service_line=service_line
    )
    if requested_category == LeaveBillingCategory.PAID:
        if suggestion.paid_days <= 0:
            raise ValueError(
                "No paid leaves available for this service line or balance — use unpaid or carry forward."
            )
        return LeaveBillingCategory.PAID
    if requested_category == LeaveBillingCategory.CARRY_FORWARD:
        if service_line != SHADOW_SERVICE_LINE and suggestion.carry_forward_days <= 0:
            raise ValueError("Carry forward applies to shadow support only.")
        return LeaveBillingCategory.CARRY_FORWARD
    if requested_category == LeaveBillingCategory.UNPAID:
        return LeaveBillingCategory.UNPAID
    if suggestion.paid_days > 0:
        return LeaveBillingCategory.PAID
    if suggestion.carry_forward_days > 0:
        return LeaveBillingCategory.CARRY_FORWARD
    return LeaveBillingCategory.UNPAID


def map_leave_type_from_billing(cat: LeaveBillingCategory) -> LeaveType:
    if cat == LeaveBillingCategory.UNPAID:
        return LeaveType.UNPAID
    return LeaveType.ANNUAL
