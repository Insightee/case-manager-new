"""Staff clock-in location and WFH quota rules."""

from __future__ import annotations

from calendar import monthrange
from datetime import date

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.timezone import today_ist
from app.models.staff_attendance import StaffAttendance, StaffWorkMode
from app.utils.geo import haversine_meters


def _wfh_count_start_date() -> date:
    raw = (settings.staff_attendance_wfh_count_from or "").strip()
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return today_ist()


def month_bounds_ist(reference: date | None = None) -> tuple[date, date]:
    ref = reference or today_ist()
    last_day = monthrange(ref.year, ref.month)[1]
    return date(ref.year, ref.month, 1), date(ref.year, ref.month, last_day)


def count_wfh_days_in_month(db: Session, user_id: int, *, month_start: date, month_end: date) -> int:
    count_from = _wfh_count_start_date()
    effective_start = max(month_start, count_from)
    if effective_start > month_end:
        return 0
    stmt = (
        select(func.count())
        .select_from(StaffAttendance)
        .where(
            StaffAttendance.user_id == user_id,
            StaffAttendance.work_mode == StaffWorkMode.WFH,
            StaffAttendance.work_date >= effective_start,
            StaffAttendance.work_date <= month_end,
            StaffAttendance.clock_in_latitude.isnot(None),
        )
    )
    return int(db.scalar(stmt) or 0)


def wfh_quota_summary(db: Session, user_id: int) -> dict:
    month_start, month_end = month_bounds_ist()
    used = count_wfh_days_in_month(db, user_id, month_start=month_start, month_end=month_end)
    limit = int(settings.staff_wfh_days_per_month)
    return {
        "wfh_days_used_this_month": used,
        "wfh_days_limit": limit,
        "wfh_days_remaining": max(0, limit - used),
        "wfh_quota_month_start": month_start.isoformat(),
        "wfh_quota_month_end": month_end.isoformat(),
    }


def validate_clock_in_location(
    *,
    work_mode: StaffWorkMode,
    latitude: float,
    longitude: float,
) -> float | None:
    if latitude < -90 or latitude > 90 or longitude < -180 or longitude > 180:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="That location snapshot did not look right — try again when the browser asks for location.",
        )

    office_lat = settings.staff_office_latitude
    office_lng = settings.staff_office_longitude
    radius = float(settings.staff_office_radius_meters)

    if work_mode == StaffWorkMode.OFFICE:
        distance = haversine_meters(latitude, longitude, office_lat, office_lng)
        if distance > radius:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Office clock-in needs you within about {int(radius)} m of {settings.staff_office_label}. "
                    "Move closer or choose work from home if you still have WFH days this month."
                ),
            )
        return distance
    return None


def assert_wfh_quota_available(db: Session, user_id: int, work_date: date) -> None:
    month_start, month_end = month_bounds_ist(work_date)
    used = count_wfh_days_in_month(db, user_id, month_start=month_start, month_end=month_end)
    limit = int(settings.staff_wfh_days_per_month)
    if used >= limit:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"You have used all {limit} work-from-home days for this month. "
                "Choose work from office when you are at the office to start today."
            ),
        )
