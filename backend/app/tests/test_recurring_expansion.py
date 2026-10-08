from datetime import date, datetime, timezone

import pytest

from app.services.recurring_expansion import (
    dates_before_start,
    expand_weekday_dates,
    ist_calendar_date,
    normalize_weekdays,
    weekday_key,
)


def test_ist_calendar_date_crosses_utc_midnight():
    # 2026-10-07 20:30 UTC is 2026-10-08 02:00 in Asia/Kolkata (Thursday).
    moment = datetime(2026, 10, 7, 20, 30, tzinfo=timezone.utc)
    day = ist_calendar_date(moment)
    assert day == date(2026, 10, 8)
    assert weekday_key(day) == "thu"


def test_normalize_weekdays_rejects_numeric_indexes():
    with pytest.raises(ValueError, match="mon, wed"):
        normalize_weekdays(["0", "2", "4"])


def test_thursday_start_flags_earlier_selected_weekdays():
    start = date(2026, 10, 8)
    assert dates_before_start(start, ["mon", "wed", "fri"]) == ["mon", "wed"]


def test_eight_week_mon_wed_fri_is_inclusive():
    start = date(2026, 10, 8)
    end = date(2026, 12, 2)  # start + (8 * 7 - 1)
    days = expand_weekday_dates(start, end, ["mon", "wed", "fri"])
    assert days[0] == date(2026, 10, 9)
    assert date(2026, 10, 5) not in days
    assert date(2026, 10, 7) not in days
    assert all(weekday_key(day) in {"mon", "wed", "fri"} for day in days)
    assert len(days) == 24
