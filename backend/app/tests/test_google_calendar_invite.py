from __future__ import annotations

from datetime import date, time

from app.services.email.google_calendar import build_google_calendar_add_url


def test_google_calendar_url_includes_ctz_and_dates():
    url = build_google_calendar_add_url(
        title="Care coordination",
        scheduled_date=date(2026, 7, 15),
        scheduled_time=time(11, 0),
        duration_minutes=45,
        details="Join: https://meet.google.com/abc",
        location="https://meet.google.com/abc",
        timezone="Asia/Kolkata",
    )
    assert url.startswith("https://calendar.google.com/calendar/render?")
    assert "action=TEMPLATE" in url
    assert "ctz=Asia%2FKolkata" in url or "ctz=Asia/Kolkata" in url
    assert "20260715T110000" in url
    assert "20260715T114500" in url
    assert "Care+coordination" in url or "Care%20coordination" in url
