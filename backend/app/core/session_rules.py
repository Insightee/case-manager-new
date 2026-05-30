"""Shared session duration and auto-logout rules for therapist visits."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

MIN_SESSION_MINUTES = 5
MIN_SESSION_DURATION_ERROR = "Session must be at least 5 minutes to be recorded."

HOMECARE_AUTO_END_HOURS = 3
SHADOW_AUTO_END_HOURS = 10
SESSION_FALLBACK_MAX_HOURS = 4


def duration_minutes_between(start: datetime, end: datetime) -> int:
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    return max(0, int((end - start).total_seconds() // 60))


def validate_session_duration_minutes(minutes: int) -> None:
    if minutes < MIN_SESSION_MINUTES:
        raise ValueError(MIN_SESSION_DURATION_ERROR)


def product_module_for_case(case) -> str:
    if case is None:
        return "homecare"
    return (getattr(case, "product_module", None) or "homecare").strip().lower()


def auto_end_threshold_for_module(product_module: str, slot_duration_minutes: int | None) -> timedelta:
    mod = (product_module or "homecare").strip().lower()
    if mod == "homecare":
        return timedelta(hours=HOMECARE_AUTO_END_HOURS)
    if mod == "shadow_support":
        return timedelta(hours=SHADOW_AUTO_END_HOURS)
    if slot_duration_minutes and slot_duration_minutes > 0:
        return timedelta(seconds=slot_duration_minutes * 60 * 1.5)
    return timedelta(hours=SESSION_FALLBACK_MAX_HOURS)


def auto_end_reason_for_module(product_module: str) -> str:
    mod = (product_module or "homecare").strip().lower()
    if mod == "homecare":
        return "homecare_3h_limit"
    if mod == "shadow_support":
        return "shadow_10h_limit"
    return "slot_duration_limit"


def auto_end_label(auto_end_reason: str | None) -> str | None:
    if not auto_end_reason:
        return None
    if auto_end_reason == "homecare_3h_limit":
        return "Auto closed — Homecare 3 hour limit"
    if auto_end_reason == "shadow_10h_limit":
        return "Auto closed — Shadow 10 hour limit"
    return "Auto closed by system"
