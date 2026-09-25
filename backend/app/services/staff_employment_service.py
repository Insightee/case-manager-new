"""Staff employment type, leave credits, and probation leave rules."""

from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.permissions import RoleName
from app.models.leave import LeaveBillingCategory, LeaveStatus
from app.models.staff_leave import StaffLeave
from app.models.user import StaffEmploymentType, User


def is_staff_employment_user(user: User) -> bool:
    roles = {str(r).upper() for r in (user.role_names or [])}
    if RoleName.THERAPIST.value in roles:
        return False
    staff_roles = {
        RoleName.SPOT.value,
        RoleName.HR.value,
        RoleName.CASE_MANAGER.value,
        RoleName.FINANCE.value,
        RoleName.MODULE_ADMIN.value,
        RoleName.ADMIN.value,
        RoleName.SUPER_ADMIN.value,
        RoleName.VIEWER.value,
        RoleName.SUPERVISOR.value,
        RoleName.SCHOOL_COORDINATOR.value,
    }
    return bool(roles & staff_roles)


def _add_months(start: date, months: int) -> date:
    month_index = start.month - 1 + int(months)
    year = start.year + month_index // 12
    month = month_index % 12 + 1
    day = min(start.day, monthrange(year, month)[1])
    return date(year, month, day)


def probation_end_date(user: User) -> date | None:
    if user.staff_employment_type != StaffEmploymentType.PROBATION:
        return None
    if not user.staff_employment_start_date or not user.staff_probation_months:
        return None
    end_exclusive = _add_months(user.staff_employment_start_date, int(user.staff_probation_months))
    return end_exclusive - timedelta(days=1)


def is_on_probation(user: User, *, as_of: date | None = None) -> bool:
    return user.staff_employment_type == StaffEmploymentType.PROBATION


def probation_calendar_ended(user: User, *, as_of: date | None = None) -> bool:
    end = probation_end_date(user)
    if end is None:
        return False
    today = as_of or date.today()
    return today > end


def validate_staff_employment_fields(
    *,
    employment_type: StaffEmploymentType | str | None,
    probation_months: int | None,
    employment_start_date: date | None,
) -> None:
    if employment_type is None:
        if probation_months is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Probation period applies only when employment type is Probation.",
            )
        return
    etype = StaffEmploymentType(employment_type) if isinstance(employment_type, str) else employment_type
    if etype == StaffEmploymentType.PROBATION:
        if not probation_months or int(probation_months) < 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Please add how many months probation lasts.",
            )
        if not employment_start_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Employment start date is needed for probation tracking.",
            )
    elif probation_months is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Probation period applies only when employment type is Probation.",
        )


def apply_staff_employment_fields(
    user: User,
    *,
    employment_type: StaffEmploymentType | str | None = None,
    probation_months: int | None = None,
    employment_start_date: date | None = None,
    leave_credit_balance: int | None = None,
    clear_unset_probation: bool = False,
) -> None:
    if employment_type is not None:
        if employment_type == "" or employment_type is None:
            user.staff_employment_type = None
        else:
            user.staff_employment_type = (
                StaffEmploymentType(employment_type) if isinstance(employment_type, str) else employment_type
            )
        if user.staff_employment_type != StaffEmploymentType.PROBATION:
            user.staff_probation_months = None
            if clear_unset_probation:
                user.staff_probation_end_notified_at = None
    if probation_months is not None:
        user.staff_probation_months = int(probation_months) if probation_months else None
    if employment_start_date is not None:
        user.staff_employment_start_date = employment_start_date
    if leave_credit_balance is not None:
        user.staff_leave_credit_balance = max(int(leave_credit_balance), 0)
    if user.staff_employment_type != StaffEmploymentType.PROBATION:
        user.staff_probation_months = None


def paid_staff_leaves_in_month(db: Session, user_id: int, year: int, month: int) -> int:
    start = date(year, month, 1)
    end = date(year, month, monthrange(year, month)[1])
    return int(
        db.scalar(
            select(func.count())
            .select_from(StaffLeave)
            .where(
                StaffLeave.staff_user_id == user_id,
                StaffLeave.status == LeaveStatus.APPROVED,
                StaffLeave.billing_category == LeaveBillingCategory.PAID,
                StaffLeave.leave_date >= start,
                StaffLeave.leave_date <= end,
            )
        )
        or 0
    )


def pending_paid_staff_leaves_in_month(db: Session, user_id: int, year: int, month: int) -> int:
    start = date(year, month, 1)
    end = date(year, month, monthrange(year, month)[1])
    return int(
        db.scalar(
            select(func.count())
            .select_from(StaffLeave)
            .where(
                StaffLeave.staff_user_id == user_id,
                StaffLeave.status == LeaveStatus.PENDING,
                StaffLeave.billing_category == LeaveBillingCategory.PAID,
                StaffLeave.leave_date >= start,
                StaffLeave.leave_date <= end,
            )
        )
        or 0
    )


def resolve_staff_leave_billing_category(db: Session, user: User, leave_date: date) -> LeaveBillingCategory:
    """Decide paid vs unpaid for a staff leave on the given date."""
    if is_on_probation(user):
        paid_count = paid_staff_leaves_in_month(db, user.id, leave_date.year, leave_date.month)
        pending_paid = pending_paid_staff_leaves_in_month(db, user.id, leave_date.year, leave_date.month)
        if paid_count + pending_paid >= 1:
            return LeaveBillingCategory.UNPAID
        return LeaveBillingCategory.PAID

    balance = int(user.staff_leave_credit_balance or 0)
    if balance <= 0:
        return LeaveBillingCategory.UNPAID
    return LeaveBillingCategory.PAID


def staff_leave_balance_summary(db: Session, user: User) -> dict:
    on_probation = is_on_probation(user)
    year = date.today().year
    month = date.today().month
    paid_used = paid_staff_leaves_in_month(db, user.id, year, month)
    pending_paid = pending_paid_staff_leaves_in_month(db, user.id, year, month)
    credits = int(user.staff_leave_credit_balance or 0)
    end = probation_end_date(user)
    return {
        "employment_type": user.staff_employment_type.value if user.staff_employment_type else None,
        "probation_months": user.staff_probation_months,
        "employment_start_date": user.staff_employment_start_date.isoformat()
        if user.staff_employment_start_date
        else None,
        "probation_end_date": end.isoformat() if end else None,
        "probation_calendar_ended": probation_calendar_ended(user),
        "leave_credit_balance": credits,
        "paid_leaves_used_this_month": paid_used,
        "pending_paid_leaves_this_month": pending_paid,
        "probation_paid_cap_per_month": 1 if on_probation else None,
        "on_probation": on_probation,
    }


def preview_staff_leave_billing_category(db: Session, user: User, leave_date: date) -> LeaveBillingCategory:
    return resolve_staff_leave_billing_category(db, user, leave_date)


def apply_staff_leave_approval(db: Session, user: User, leave: StaffLeave) -> None:
    if leave.status != LeaveStatus.APPROVED:
        return
    if leave.billing_category != LeaveBillingCategory.PAID:
        return
    if is_on_probation(user):
        return
    current = int(user.staff_leave_credit_balance or 0)
    if current <= 0:
        leave.billing_category = LeaveBillingCategory.UNPAID
        return
    user.staff_leave_credit_balance = current - 1


def staff_users_with_ended_probation(db: Session) -> list[User]:
    today = date.today()
    rows = db.scalars(
        select(User).where(
            User.staff_employment_type == StaffEmploymentType.PROBATION,
            User.staff_employment_start_date.isnot(None),
            User.staff_probation_months.isnot(None),
        )
    ).all()
    out: list[User] = []
    for user in rows:
        end = probation_end_date(user)
        if end and today > end:
            out.append(user)
    return out


def staff_users_pending_probation_notification(db: Session) -> list[User]:
    return [u for u in staff_users_with_ended_probation(db) if u.staff_probation_end_notified_at is None]
