from __future__ import annotations

import csv
import io
from collections import defaultdict
from datetime import date, timedelta
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.permissions import RoleName, user_has_permission
from app.models.leave import LeaveBillingCategory, LeaveStatus, LeaveType, TherapistLeave
from app.models.role import Role
from app.models.user import User
from app.services import leave_dates_service as leave_dates
from app.services import leave_migration_service as leave_migration
from app.services import leave_notification_service as leave_notify
from app.services import leave_policy_service as policy
from app.services.therapist_profile_service import get_or_create_profile


def leave_day_count(start: date, end: date) -> int:
    return (end - start).days + 1


def days_in_calendar_year(
    leave: TherapistLeave,
    year: int,
    db: Session | None = None,
    *,
    shadow_only: bool = False,
) -> int:
    if leave.status != LeaveStatus.APPROVED:
        return 0
    year_start = date(year, 1, 1)
    year_end = date(year, 12, 31)
    start = max(leave.start_date, year_start)
    end = min(leave.end_date, year_end)
    if end < start:
        return 0
    if db is not None:
        return len(
            leave_dates.billable_leave_dates(
                db, leave, from_date=start, to_date=end, shadow_only=shadow_only
            )
        )
    return (end - start).days + 1


def leave_overlaps_year(leave: TherapistLeave, year: int) -> bool:
    year_start = date(year, 1, 1)
    year_end = date(year, 12, 31)
    return leave.start_date <= year_end and leave.end_date >= year_start


def users_with_leave_manage(db: Session, *, exclude_user_id: Optional[int] = None) -> list[User]:
    users = db.scalars(
        select(User).options(selectinload(User.roles).selectinload(Role.permissions))
    ).all()
    out: list[User] = []
    for u in users:
        if exclude_user_id and u.id == exclude_user_id:
            continue
        if user_has_permission(u, "leave.manage"):
            out.append(u)
    return out


def build_summary(
    db: Session,
    *,
    year: int,
    therapist_user_id: Optional[int] = None,
) -> dict:
    stmt = select(TherapistLeave).order_by(TherapistLeave.start_date.desc())
    if therapist_user_id is not None:
        stmt = stmt.where(TherapistLeave.therapist_user_id == therapist_user_id)
    leaves = db.scalars(stmt).all()
    year_leaves = [l for l in leaves if leave_overlaps_year(l, year)]

    by_type: dict[str, int] = defaultdict(int)
    pending = rejected = 0
    approved_days = 0
    entries: list[dict] = []

    for l in year_leaves:
        if l.status == LeaveStatus.PENDING:
            pending += 1
        elif l.status == LeaveStatus.REJECTED:
            rejected += 1
        days = days_in_calendar_year(l, year, db)
        if l.status == LeaveStatus.APPROVED:
            approved_days += days
            by_type[l.leave_type.value] += days
        entries.append(
            {
                "id": l.id,
                "leave_type": l.leave_type.value,
                "start_date": l.start_date.isoformat(),
                "end_date": l.end_date.isoformat(),
                "status": l.status.value,
                "day_count": leave_day_count(l.start_date, l.end_date),
                "days_in_year": days,
                "review_note": l.review_note,
            }
        )

    return {
        "year": year,
        "approved_days": approved_days,
        "days_by_type": dict(by_type),
        "pending_count": pending,
        "rejected_count": rejected,
        "entries": entries,
    }


def build_report(
    db: Session,
    *,
    year: int,
    granularity: str = "monthly",
) -> list[dict]:
    leaves = db.scalars(select(TherapistLeave).order_by(TherapistLeave.therapist_user_id)).all()
    therapist_names: dict[int, str] = {}
    rows: list[dict] = []

    for l in leaves:
        if not leave_overlaps_year(l, year):
            continue
        if l.therapist_user_id not in therapist_names:
            t = db.get(User, l.therapist_user_id)
            therapist_names[l.therapist_user_id] = t.full_name if t else f"User #{l.therapist_user_id}"

        if granularity == "yearly":
            period = str(year)
            days = days_in_calendar_year(l, year, db) if l.status == LeaveStatus.APPROVED else 0
            rows.append(
                {
                    "therapist_user_id": l.therapist_user_id,
                    "therapist_name": therapist_names[l.therapist_user_id],
                    "period": period,
                    "leave_type": l.leave_type.value,
                    "status": l.status.value,
                    "days": days,
                    "start_date": l.start_date.isoformat(),
                    "end_date": l.end_date.isoformat(),
                }
            )
            continue

        # monthly: split approved days across months touched
        for month in range(1, 13):
            month_start = date(year, month, 1)
            if month == 12:
                month_end = date(year, 12, 31)
            else:
                month_end = date(year, month + 1, 1) - timedelta(days=1)

            if l.start_date > month_end or l.end_date < month_start:
                continue
            if l.status != LeaveStatus.APPROVED:
                rows.append(
                    {
                        "therapist_user_id": l.therapist_user_id,
                        "therapist_name": therapist_names[l.therapist_user_id],
                        "period": f"{year}-{month:02d}",
                        "leave_type": l.leave_type.value,
                        "status": l.status.value,
                        "days": 0,
                        "start_date": l.start_date.isoformat(),
                        "end_date": l.end_date.isoformat(),
                    }
                )
                continue
            start = max(l.start_date, month_start)
            end = min(l.end_date, month_end)
            days = len(
                leave_dates.billable_leave_dates(db, l, from_date=start, to_date=end)
            )
            rows.append(
                {
                    "therapist_user_id": l.therapist_user_id,
                    "therapist_name": therapist_names[l.therapist_user_id],
                    "period": f"{year}-{month:02d}",
                    "leave_type": l.leave_type.value,
                    "status": l.status.value,
                    "days": days,
                    "start_date": l.start_date.isoformat(),
                    "end_date": l.end_date.isoformat(),
                }
            )

    return rows


def report_to_csv(rows: list[dict]) -> str:
    buf = io.StringIO()
    fieldnames = [
        "therapist_name",
        "therapist_user_id",
        "period",
        "leave_type",
        "status",
        "days",
        "start_date",
        "end_date",
    ]
    writer = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return buf.getvalue()


def _leave_case_ids(leave: TherapistLeave) -> list[int]:
    ids = [int(x) for x in (leave.case_ids or [])]
    if leave.case_id is not None and int(leave.case_id) not in ids:
        ids.insert(0, int(leave.case_id))
    return ids


def _leave_scope_ids(leave: TherapistLeave) -> set[int] | None:
    """None means therapist-wide leave."""
    ids = _leave_case_ids(leave)
    return set(ids) if ids else None


def _leave_scopes_conflict(existing: TherapistLeave, new_case_ids: list[int] | None) -> bool:
    existing_scope = _leave_scope_ids(existing)
    new_scope = set(new_case_ids) if new_case_ids else None
    if existing_scope is None or new_scope is None:
        return True
    return bool(existing_scope & new_scope)


def create_therapist_leave_request(
    db: Session,
    *,
    therapist: User,
    start_date: date,
    end_date: date,
    case_ids: list[int] | None = None,
    case_id: int | None = None,
    service_line: str | None = None,
    billing_category: LeaveBillingCategory | None = None,
    reason: str | None = None,
    leave_type: LeaveType | None = None,
    consulted_with_parents: bool = False,
    auto_approve: bool = False,
    reviewer_user_id: int | None = None,
) -> TherapistLeave:
    """Create one leave row (possibly spanning multiple cases)."""
    if end_date < start_date:
        raise ValueError("end_date must be on or after start_date")
    if RoleName.THERAPIST.value not in therapist.role_names:
        raise ValueError("Target user is not a therapist")

    # Lock therapist User row for update to serialize concurrent leave requests for this therapist.
    db.scalars(select(User).where(User.id == therapist.id).with_for_update()).first()
    
    # Gating duplicate leaves on overlapping date ranges.
    # Use with_for_update() to prevent race conditions from concurrent rapid
    # requests (e.g. fast calendar taps on mobile).
    svc = (service_line or "").strip().lower() or "shadow_support"
    overlap_stmt = (
        select(TherapistLeave)
        .where(
            TherapistLeave.therapist_user_id == therapist.id,
            TherapistLeave.status.in_([LeaveStatus.PENDING, LeaveStatus.APPROVED]),
            TherapistLeave.start_date <= end_date,
            TherapistLeave.end_date >= start_date,
        )
        .with_for_update()
    )
    overlapping_leaves = db.scalars(overlap_stmt).all()
    ids = list(dict.fromkeys(int(x) for x in (case_ids or [])))
    if case_id is not None and int(case_id) not in ids:
        ids.insert(0, int(case_id))
    leave_dates.lock_leave_and_absence_rows(db, therapist.id)
    leave_dates.raise_if_absence_blocks_leave(
        db,
        therapist_user_id=therapist.id,
        start=start_date,
        end=end_date,
        case_ids=ids or None,
    )
    conflicting = [lv for lv in overlapping_leaves if _leave_scopes_conflict(lv, ids or None)]
    if conflicting:
        conflict = conflicting[0]
        conflict_dates = (
            conflict.start_date.isoformat()
            if conflict.start_date == conflict.end_date
            else f"{conflict.start_date.isoformat()} to {conflict.end_date.isoformat()}"
        )
        raise ValueError(
            f"Leave already exists for {conflict_dates} (status: {conflict.status.value}). "
            f"Please cancel the existing leave first if you need to resubmit."
        )

    # Attach a non-blocking warning count of scheduled/in-progress sessions in range.
    # Callers may surface this to the user before finalising leave.
    from app.models.session import Session as TherapySession
    from app.models.session import SessionStatus as _SS
    from sqlalchemy import func as _func

    sessions_in_range: int = db.scalar(
        select(_func.count(TherapySession.id)).where(
            TherapySession.therapist_user_id == therapist.id,
            TherapySession.scheduled_date >= start_date,
            TherapySession.scheduled_date <= end_date,
            TherapySession.status.in_([_SS.SCHEDULED, _SS.IN_PROGRESS]),
        )
    ) or 0

    if not auto_approve:
        leave_migration.validate_therapist_leave_dates(start_date, end_date)

    get_or_create_profile(db, therapist.id)

    has_shadow = False
    has_homecare = False
    if ids:
        _, has_shadow, has_homecare = policy.resolve_case_context(db, therapist.id, ids)

    line = (service_line or policy.primary_service_line(has_shadow, has_homecare)).strip().lower()

    billing, paid_days, unpaid_days, includes_shadow = policy.resolve_billing_category(
        db,
        therapist,
        start_date=start_date,
        end_date=end_date,
        service_line=line,
        case_ids=ids or None,
        requested_category=billing_category,
    )
    resolved_type = leave_type or policy.map_leave_type_from_billing(billing)

    leave = TherapistLeave(
        therapist_user_id=therapist.id,
        leave_type=resolved_type,
        service_line=line,
        billing_category=billing,
        case_id=ids[0] if ids else None,
        case_ids=ids or None,
        paid_days=paid_days,
        unpaid_days=unpaid_days,
        includes_shadow_cases=includes_shadow,
        consulted_with_parents=bool(consulted_with_parents),
        start_date=start_date,
        end_date=end_date,
        reason=(reason or "").strip() or None,
        status=LeaveStatus.APPROVED if auto_approve else LeaveStatus.PENDING,
    )
    if auto_approve and reviewer_user_id:
        leave.reviewed_by_user_id = reviewer_user_id

    db.add(leave)
    db.flush()

    # Surface session conflict count as a transient attribute for callers to include in responses.
    leave._sessions_in_range = sessions_in_range  # type: ignore[attr-defined]

    if auto_approve:
        leave_notify.notify_leave_approved(db, leave, therapist)
    else:
        leave_notify.notify_leave_submitted(db, leave, therapist)

    return leave
