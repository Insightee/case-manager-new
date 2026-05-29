"""Google Calendar "Add event" links for meeting invite emails."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from urllib.parse import urlencode

from app.core.config import settings


def build_google_calendar_add_url(
    *,
    title: str,
    scheduled_date: date,
    scheduled_time: time | None,
    duration_minutes: int,
    details: str = "",
    location: str = "",
    timezone: str | None = None,
) -> str:
    """
    Build a Google Calendar event template URL.

    Uses the `ctz` parameter so local wall-clock times match the org timezone
    (configurable via MEETING_INVITE_CALENDAR_TIMEZONE, default Asia/Kolkata).
    """
    tz = (timezone or settings.meeting_invite_calendar_timezone or "Asia/Kolkata").strip()
    start = datetime.combine(scheduled_date, scheduled_time or time(9, 0))
    end = start + timedelta(minutes=max(int(duration_minutes or 30), 15))
    fmt = "%Y%m%dT%H%M%S"
    params: dict[str, str] = {
        "action": "TEMPLATE",
        "text": (title or "Meeting")[:1024],
        "dates": f"{start.strftime(fmt)}/{end.strftime(fmt)}",
        "ctz": tz,
    }
    if details.strip():
        params["details"] = details.strip()[:5000]
    if location.strip():
        params["location"] = location.strip()[:1024]
    return f"https://calendar.google.com/calendar/render?{urlencode(params)}"
