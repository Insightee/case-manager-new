from __future__ import annotations

from datetime import date, datetime, time
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")


def now_ist() -> datetime:
    return datetime.now(IST)


def today_ist() -> date:
    return now_ist().date()


def ensure_utc_aware(dt: datetime | None) -> datetime | None:
    """Attach UTC tz to naive datetimes from SQLite before JSON serialization."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=ZoneInfo("UTC"))
    return dt


def wall_clock_time_ist(dt: datetime | None) -> time | None:
    """IST wall-clock time for session start_time / end_time columns."""
    if dt is None:
        return None
    aware = ensure_utc_aware(dt)
    assert aware is not None
    return aware.astimezone(IST).time().replace(second=0, microsecond=0)
