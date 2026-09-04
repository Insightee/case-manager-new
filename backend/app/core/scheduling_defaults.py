from __future__ import annotations

from datetime import time
from typing import Any

WEEKDAY_KEYS: list[str] = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
KEY_TO_WEEKDAY: dict[str, int] = {key: index for index, key in enumerate(WEEKDAY_KEYS)}
WEEKDAY_TO_KEY: dict[int, str] = {index: key for index, key in enumerate(WEEKDAY_KEYS)}

WEEKDAY_DEFAULT_WINDOW = (time(10, 0), time(19, 0))
WEEKEND_DEFAULT_WINDOW = (time(9, 0), time(18, 0))
SESSION_SLOT_DEFAULT_WINDOW = (time(8, 0), time(20, 0))


def weekends_enabled() -> bool:
    from app.core.config import settings

    return bool(settings.scheduling_weekends_enabled)


def default_weekday_indices() -> list[int]:
    if weekends_enabled():
        return list(range(7))
    return list(range(5))


def default_open_windows() -> dict[int, list[tuple[time, time]]]:
    windows: dict[int, list[tuple[time, time]]] = {
        weekday: [WEEKDAY_DEFAULT_WINDOW] for weekday in range(5)
    }
    if weekends_enabled():
        windows[5] = [WEEKEND_DEFAULT_WINDOW]
        windows[6] = [WEEKEND_DEFAULT_WINDOW]
    return windows


def default_schedule_days() -> dict[str, dict[str, Any]]:
    days: dict[str, dict[str, Any]] = {}
    for index, key in enumerate(WEEKDAY_KEYS):
        enabled = index < 5 or weekends_enabled()
        if index < 5:
            start, end = SESSION_SLOT_DEFAULT_WINDOW
        else:
            start, end = WEEKEND_DEFAULT_WINDOW
        days[key] = {
            "enabled": enabled,
            "start": start.strftime("%H:%M"),
            "end": end.strftime("%H:%M"),
        }
    return days


def default_template_config() -> dict[str, Any]:
    return {
        "timezone": "Asia/Kolkata",
        "slot_duration_minutes": 60,
        "days": {key: dict(value) for key, value in default_schedule_days().items()},
    }
