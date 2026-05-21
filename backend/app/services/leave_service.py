from __future__ import annotations

import csv
import io
from collections import defaultdict
from datetime import date, timedelta
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.permissions import user_has_permission
from app.models.leave import LeaveStatus, LeaveType, TherapistLeave
from app.models.role import Role
from app.models.user import User


def leave_day_count(start: date, end: date) -> int:
    return (end - start).days + 1


def days_in_calendar_year(leave: TherapistLeave, year: int) -> int:
    if leave.status != LeaveStatus.APPROVED:
        return 0
    year_start = date(year, 1, 1)
    year_end = date(year, 12, 31)
    start = max(leave.start_date, year_start)
    end = min(leave.end_date, year_end)
    if end < start:
        return 0
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
        days = days_in_calendar_year(l, year)
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
            days = days_in_calendar_year(l, year) if l.status == LeaveStatus.APPROVED else 0
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
            days = (end - start).days + 1
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
