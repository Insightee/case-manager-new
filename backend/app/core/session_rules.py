"""Session duration caps, auto-end reasons, and schedule-aware auto-close rules."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from app.core.clinical_service_resolver import (
    product_module_for_case,
    resolve_clinical_service_category,
)
from app.core.timezone import ensure_utc_aware

IST = ZoneInfo("Asia/Kolkata")

MIN_SESSION_MINUTES = 1
MIN_SESSION_DURATION_ERROR = "Session duration must be at least 1 minute."

# Sessions started within this window (minutes from actual_start_at) and with no
# log/ledger/absence dependencies can be cancelled as "accidentally started".
ACCIDENTAL_START_WINDOW_MINUTES = 5

# Legacy module ceilings (unscheduled absolute caps from actual start).
SHADOW_MAX_HOURS = 10
HOMECARE_MAX_HOURS = 3
SESSION_FALLBACK_MAX_HOURS = 4

SCHEDULED_DURATION_MULTIPLIER = 3.0
SHADOW_SCHEDULED_END_BUFFER_HOURS = 2
HOMECARE_SCHEDULED_END_BUFFER_MINUTES = 45

# Category default max duration when no scheduled_end_at (hours from actual_start).
CATEGORY_DEFAULT_MAX_HOURS: dict[str, float] = {
    "homecare": HOMECARE_MAX_HOURS,
    "shadow_support": SHADOW_MAX_HOURS,
    "school_support": SHADOW_MAX_HOURS,
    "special_education": 4.0,
    "behavior_therapy": 3.0,
    "play_therapy": 3.0,
    "counselling": 2.0,
    "other_clinical": SESSION_FALLBACK_MAX_HOURS,
    "unknown": SESSION_FALLBACK_MAX_HOURS,
}

# Buffer after scheduled_end before auto-close (minutes).
CATEGORY_AFTER_SCHEDULE_BUFFER_MINUTES: dict[str, int] = {
    "homecare": HOMECARE_SCHEDULED_END_BUFFER_MINUTES,
    "shadow_support": SHADOW_SCHEDULED_END_BUFFER_HOURS * 60,
    "school_support": SHADOW_SCHEDULED_END_BUFFER_HOURS * 60,
    "special_education": 60,
    "behavior_therapy": 60,
    "play_therapy": 60,
    "counselling": 30,
    "other_clinical": 60,
    "unknown": 60,
}

AUTO_END_REASON_LABELS: dict[str, str] = {
    "homecare_3h_limit": "Auto closed after homecare duration limit",
    "homecare_duration_limit": "Auto closed after homecare duration limit",
    "shadow_10h_limit": "Auto closed after scheduled school window",
    "shadow_wall_clock_cap": "Auto closed after scheduled school window",
    "scheduled_window_cap": "Auto closed after expected session duration",
    "scheduled_duration_exceeded": "Auto closed after expected session duration",
    "category_duration_limit": "Auto closed after service duration limit",
    "slot_duration_limit": "Auto closed — safety duration limit",
    "day_end_10pm_ist": "Auto closed at day end",
    "day_end": "Auto closed at day end",
    "historical_cleanup_at_day_end": "Previous session auto-closed at day end — complete your log when ready",
}

EARLY_CLOSE_ANOMALY_HINT = (
    "Auto-close happened before scheduled end. Please review service category."
)


def _combine_ist(d: date, t: time) -> datetime:
    return datetime.combine(d, t, tzinfo=IST)


def _time_to_minutes(t: time | None) -> int | None:
    if t is None:
        return None
    return t.hour * 60 + t.minute


def validate_session_duration_minutes(minutes: int) -> None:
    if minutes < MIN_SESSION_MINUTES:
        raise ValueError(MIN_SESSION_DURATION_ERROR)


def scheduled_duration_minutes(
    scheduled_date: date | None = None,
    start_time: time | None = None,
    end_time: time | None = None,
    *,
    slot_duration_minutes: int | None = None,
) -> int:
    if scheduled_date is not None and start_time is not None and end_time is not None:
        start = _combine_ist(scheduled_date, start_time)
        end = _combine_ist(scheduled_date, end_time)
        if end <= start:
            end += timedelta(days=1)
        return max(1, int((end - start).total_seconds() // 60))
    start_m = _time_to_minutes(start_time)
    end_m = _time_to_minutes(end_time)
    if start_m is not None and end_m is not None and end_m > start_m:
        return end_m - start_m
    if slot_duration_minutes and slot_duration_minutes > 0:
        return int(slot_duration_minutes)
    return 60


def scheduled_end_at_utc(
    scheduled_date: date | None,
    end_time: time | None,
) -> datetime | None:
    if scheduled_date is None or end_time is None:
        return None
    return _combine_ist(scheduled_date, end_time).astimezone(timezone.utc)


def scheduled_start_at_utc(
    scheduled_date: date | None,
    start_time: time | None,
) -> datetime | None:
    if scheduled_date is None or start_time is None:
        return None
    return _combine_ist(scheduled_date, start_time).astimezone(timezone.utc)


def duration_minutes_between(start: datetime, end: datetime) -> int:
    start_utc = ensure_utc_aware(start)
    end_utc = ensure_utc_aware(end)
    return max(0, int((end_utc - start_utc).total_seconds() // 60))


def _category_buffer_minutes(category: str) -> int:
    return CATEGORY_AFTER_SCHEDULE_BUFFER_MINUTES.get(category, 60)


def _category_default_hours(category: str) -> float:
    return CATEGORY_DEFAULT_MAX_HOURS.get(category, SESSION_FALLBACK_MAX_HOURS)


def auto_end_reason_for_category(category: str, *, scheduled: bool) -> str:
    if scheduled:
        if category in ("shadow_support", "school_support"):
            return "shadow_wall_clock_cap"
        if category == "homecare":
            return "homecare_duration_limit"
        return "scheduled_window_cap"
    if category == "homecare":
        return "homecare_3h_limit"
    if category in ("shadow_support", "school_support"):
        return "shadow_10h_limit"
    if category == "unknown":
        return "slot_duration_limit"
    return "category_duration_limit"


def auto_end_reason_for_module(product_module: str) -> str:
    """Legacy helper; prefer auto_end_reason_for_category."""
    category = resolve_clinical_service_category(None, product_module=product_module)
    return auto_end_reason_for_category(category, scheduled=False)


def auto_end_label(
    auto_end_reason: str | None,
    *,
    overage_mins: int | None = None,
    scheduled_end_at: datetime | None = None,
    actual_end_at: datetime | None = None,
) -> str | None:
    if not auto_end_reason:
        return None
    base = AUTO_END_REASON_LABELS.get(auto_end_reason, "Auto closed by system")
    if (
        auto_end_reason in ("slot_duration_limit", "category_duration_limit")
        and scheduled_end_at is not None
        and actual_end_at is not None
        and ensure_utc_aware(actual_end_at) < ensure_utc_aware(scheduled_end_at)
    ):
        return f"{base} — {EARLY_CLOSE_ANOMALY_HINT}"
    if overage_mins is not None and overage_mins > 0:
        return f"{base} (+{overage_mins} min past scheduled end)"
    return base


def auto_end_label_for_reason(
    auto_end_reason: str | None,
    overage_mins: int | None = None,
    *,
    scheduled_end_at: datetime | None = None,
    actual_end_at: datetime | None = None,
) -> str | None:
    return auto_end_label(
        auto_end_reason,
        overage_mins=overage_mins,
        scheduled_end_at=scheduled_end_at,
        actual_end_at=actual_end_at,
    )


def _enforce_scheduled_floor(
    candidates: list[tuple[datetime, str]],
    scheduled_end: datetime,
) -> list[tuple[datetime, str]]:
    """Drop or lift caps that would close before scheduled_end."""
    floor = ensure_utc_aware(scheduled_end)
    adjusted: list[tuple[datetime, str]] = []
    for cap_at, reason in candidates:
        cap_at = ensure_utc_aware(cap_at)
        if cap_at < floor:
            continue
        adjusted.append((cap_at, reason))
    return adjusted


def compute_auto_end_cap(
    *,
    started_at: datetime,
    scheduled_date: date | None,
    start_time: time | None,
    end_time: time | None,
    product_module: str,
    service_category: str | None = None,
) -> tuple[datetime, str, int, int]:
    """
    Return (hard_cap_utc, auto_end_reason, scheduled_duration_mins, overage_mins).

  When scheduled_end_at exists, final cap is never earlier than scheduled_end_at.
  Day-end 10 PM IST closure is handled separately in session_day_end_service.
    """
    started = ensure_utc_aware(started_at)
    category = service_category or resolve_clinical_service_category(
        None, product_module=product_module
    )
    sched_mins = scheduled_duration_minutes(scheduled_date, start_time, end_time)
    sched_mins = max(1, sched_mins)
    sched_end = scheduled_end_at_utc(scheduled_date, end_time)
    sched_start = scheduled_start_at_utc(scheduled_date, start_time)

    if sched_end is not None and sched_end > started:
        buffer = timedelta(minutes=_category_buffer_minutes(category))
        schedule_cap = sched_end + buffer
        reason = auto_end_reason_for_category(category, scheduled=True)
        candidates: list[tuple[datetime, str]] = [(schedule_cap, reason)]

        duration_cap = started + timedelta(minutes=int(sched_mins * SCHEDULED_DURATION_MULTIPLIER))
        if duration_cap > schedule_cap:
            candidates.append((duration_cap, "scheduled_duration_exceeded"))

        candidates = _enforce_scheduled_floor(candidates, sched_end)
        if not candidates:
            candidates = [(sched_end + buffer, reason)]

        hard_cap, reason = min(candidates, key=lambda x: x[0])
        expected_end = sched_end
    else:
        default_hours = _category_default_hours(category)
        hard_cap = started + timedelta(hours=default_hours)
        reason = auto_end_reason_for_category(category, scheduled=False)
        expected_end = sched_start + timedelta(minutes=sched_mins) if sched_start else started + timedelta(
            minutes=sched_mins
        )

    overage = duration_minutes_between(expected_end, hard_cap)
    return hard_cap, reason, sched_mins, max(0, overage)


def module_absolute_ceiling(started_at: datetime, product_module: str) -> datetime:
    """Legacy: unscheduled category max from actual start."""
    started = ensure_utc_aware(started_at)
    category = resolve_clinical_service_category(None, product_module=product_module)
    hours = _category_default_hours(category)
    return started + timedelta(hours=hours)


__all__ = [
    "ACCIDENTAL_START_WINDOW_MINUTES",
    "AUTO_END_REASON_LABELS",
    "CATEGORY_AFTER_SCHEDULE_BUFFER_MINUTES",
    "CATEGORY_DEFAULT_MAX_HOURS",
    "EARLY_CLOSE_ANOMALY_HINT",
    "HOMECARE_MAX_HOURS",
    "MIN_SESSION_DURATION_ERROR",
    "MIN_SESSION_MINUTES",
    "SESSION_FALLBACK_MAX_HOURS",
    "SHADOW_MAX_HOURS",
    "auto_end_label",
    "auto_end_label_for_reason",
    "auto_end_reason_for_category",
    "auto_end_reason_for_module",
    "compute_auto_end_cap",
    "duration_minutes_between",
    "module_absolute_ceiling",
    "product_module_for_case",
    "resolve_clinical_service_category",
    "scheduled_duration_minutes",
    "scheduled_end_at_utc",
    "scheduled_start_at_utc",
    "validate_session_duration_minutes",
]
