"""Calendar-date expansion for recurring session bookings.

Dates are civil calendar days (not timestamps). Weekday keys are Monday-first
(`mon` = Monday), matching `date.weekday()`. Numeric indexes are rejected
because Sunday-0 and Monday-0 cannot be told apart.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.core.scheduling_defaults import WEEKDAY_KEYS

IST = ZoneInfo("Asia/Kolkata")

_ALIASES: dict[str, str] = {}
for _key, _names in {
    "mon": ("m", "mo", "mon", "monday"),
    "tue": ("tu", "tue", "tues", "tuesday"),
    "wed": ("w", "we", "wed", "wednesday"),
    "thu": ("th", "thu", "thur", "thurs", "thursday"),
    "fri": ("f", "fr", "fri", "friday"),
    "sat": ("sa", "sat", "saturday"),
    "sun": ("su", "sun", "sunday"),
}.items():
    for _name in _names:
        _ALIASES[_name] = _key


def weekday_key(day: date) -> str:
    return WEEKDAY_KEYS[day.weekday()]


def ist_calendar_date(moment: datetime) -> date:
    """Civil date in Asia/Kolkata. Naive values are treated as UTC."""
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(IST).date()


def normalize_weekdays(weekdays: list[str]) -> list[str]:
    if not weekdays:
        raise ValueError("Select at least one weekday")
    normalized: list[str] = []
    unknown: list[str] = []
    for raw in weekdays:
        text = str(raw).strip().lower()
        key = _ALIASES.get(text)
        if key is None:
            unknown.append(str(raw))
            continue
        if key not in normalized:
            normalized.append(key)
    if unknown:
        joined = ", ".join(unknown)
        raise ValueError(
            f"Weekdays need names such as mon, wed, and fri. Not recognized: {joined}."
        )
    if not normalized:
        raise ValueError("Select at least one weekday")
    return normalized


def expand_weekday_dates(start: date, end: date, weekdays: list[str]) -> list[date]:
    """Every selected weekday from start through end, inclusive."""
    if end < start:
        raise ValueError("end_date must be on or after start_date")
    keys = set(normalize_weekdays(weekdays))
    out: list[date] = []
    cursor = start
    while cursor <= end:
        if weekday_key(cursor) in keys:
            out.append(cursor)
        cursor += timedelta(days=1)
    return out


class RecurringAssignResult:
    def __init__(self, record, skipped: list[dict], outside_week: list[str]):
        self.record = record
        self.skipped = skipped
        self.outside_week = outside_week


def dates_before_start(start: date, weekdays: list[str]) -> list[str]:
    """Selected weekdays that already occurred earlier in the start date's week.

    Monday is the first day of that week. Those dates are outside
    [start, end] on purpose; callers should tell the user instead of
    dropping them quietly.
    """
    keys = normalize_weekdays(weekdays)
    start_index = start.weekday()
    return [key for key in keys if WEEKDAY_KEYS.index(key) < start_index]
