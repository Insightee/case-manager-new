"""Shared session duration, auto-logout, and schedule-aware cap rules."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from app.core.timezone import IST, ensure_utc_aware

MIN_SESSION_MINUTES = 0
MIN_SESSION_DURATION_ERROR = "Session duration must be positive."

HOMECARE_AUTO_END_HOURS = 3
SHADOW_AUTO_END_HOURS = 10
SESSION_FALLBACK_MAX_HOURS = 4
SCHEDULED_DURATION_MULTIPLIER = 3.0
SHADOW_POST_END_BUFFER_HOURS = 2


def duration_minutes_between(start: datetime, end: datetime) -> int:
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    return max(0, int((end - start).total_seconds() // 60))


def validate_session_duration_minutes(minutes: int) -> None:
    if minutes < 0:
        raise ValueError(MIN_SESSION_DURATION_ERROR)


def product_module_for_case(case) -> str:
    if case is None:
        return "homecare"
    return (getattr(case, "product_module", None) or "homecare").strip().lower()


def _time_to_minutes(t: time | None) -> int | None:
    if t is None:
        return None
    return t.hour * 60 + t.minute


def scheduled_duration_minutes(
    *,
    start_time: time | None,
    end_time: time | None,
    slot_duration_minutes: int | None,
) -> int:
    start_m = _time_to_minutes(start_time)
    end_m = _time_to_minutes(end_time)
    if start_m is not None and end_m is not None and end_m > start_m:
        return end_m - start_m
    if slot_duration_minutes and slot_duration_minutes > 0:
        return int(slot_duration_minutes)
    return 60


def _combine_ist(service_date: date, wall_time: time) -> datetime:
    return datetime(
        service_date.year,
        service_date.month,
        service_date.day,
        wall_time.hour,
        wall_time.minute,
        tzinfo=IST,
    )


def module_absolute_ceiling(module: str, started_at: datetime) -> timedelta:
    mod = (module or "homecare").strip().lower()
    if mod == "homecare":
        return timedelta(hours=HOMECARE_AUTO_END_HOURS)
    if mod == "shadow_support":
        return timedelta(hours=SHADOW_AUTO_END_HOURS)
    return timedelta(hours=SESSION_FALLBACK_MAX_HOURS)


def compute_auto_end_cap(
    *,
    started_at: datetime,
    scheduled_date: date,
    start_time: time | None,
    end_time: time | None,
    slot_duration_minutes: int | None,
    product_module: str,
) -> tuple[datetime, str, int, int]:
    """
    Return (hard_cap_utc, reason, scheduled_mins, overage_mins_at_cap).
    """
    started = ensure_utc_aware(started_at)
    assert started is not None
    sched_mins = max(
        1,
        scheduled_duration_minutes(
            start_time=start_time,
            end_time=end_time,
            slot_duration_minutes=slot_duration_minutes,
        ),
    )
    duration_cap = started + timedelta(minutes=int(sched_mins * SCHEDULED_DURATION_MULTIPLIER))

    caps: list[tuple[datetime, str]] = [(duration_cap, "scheduled_duration_exceeded")]

    mod = (product_module or "homecare").strip().lower()
    if mod == "shadow_support" and end_time is not None:
        wall_cap = _combine_ist(scheduled_date, end_time) + timedelta(hours=SHADOW_POST_END_BUFFER_HOURS)
        wall_cap_utc = wall_cap.astimezone(timezone.utc)
        if wall_cap_utc > started:
            caps.append((wall_cap_utc, "shadow_wall_clock_cap"))

    module_cap = started + module_absolute_ceiling(mod, started)
    caps.append((module_cap, auto_end_reason_for_module(mod)))

    hard_cap, reason = min(caps, key=lambda item: item[0])
    expected_end = started + timedelta(minutes=sched_mins)
    overage = duration_minutes_between(expected_end, hard_cap)
    return hard_cap, reason, sched_mins, max(0, overage)


def auto_end_threshold_for_module(product_module: str, slot_duration_minutes: int | None) -> timedelta:
    """Legacy helper — absolute module ceiling from clock-in."""
    mod = (product_module or "homecare").strip().lower()
    return module_absolute_ceiling(mod, datetime.now(timezone.utc))


def auto_end_reason_for_module(product_module: str) -> str:
    mod = (product_module or "homecare").strip().lower()
    if mod == "homecare":
        return "homecare_3h_limit"
    if mod == "shadow_support":
        return "shadow_10h_limit"
    return "slot_duration_limit"


def auto_end_label(
    auto_end_reason: str | None,
    *,
    overage_mins: int | None = None,
) -> str | None:
    if not auto_end_reason:
        return None
    if auto_end_reason == "scheduled_duration_exceeded":
        if overage_mins and overage_mins > 0:
            return f"Session exceeded scheduled time by {overage_mins} minutes — confirm end time in your log"
        return "Session exceeded scheduled time — confirm end time in your log"
    if auto_end_reason == "shadow_wall_clock_cap":
        if overage_mins and overage_mins > 0:
            return f"Session auto-closed at school-day cap ({overage_mins} min over scheduled) — confirm in your log"
        return "Session auto-closed at school-day cap — confirm end time in your log"
    if auto_end_reason == "homecare_3h_limit":
        return "Auto closed — Homecare 3 hour limit"
    if auto_end_reason == "shadow_10h_limit":
        return "Auto closed — Shadow 10 hour limit"
    if auto_end_reason == "day_end_10pm_ist":
        return "Auto closed at 10 PM IST — complete your log when ready"
    if auto_end_reason == "historical_cleanup_at_day_end":
        return "Previous session auto-closed at day end — complete your log when ready"
    return "Auto closed by system"
