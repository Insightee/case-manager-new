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


def test_recurring_summary_does_not_list_already_booked_as_left_off():
    from datetime import date, time
    from types import SimpleNamespace

    from app.services.appointment_notification_service import _recurring_summary_body

    case = SimpleNamespace(child=SimpleNamespace(full_name="Kid A"), case_code="C-1")
    record = SimpleNamespace(
        get_weekdays=lambda: ["mon", "wed"],
        start_time=time(10, 0),
        end_time=time(11, 0),
        start_date=date(2026, 10, 12),
        end_date=date(2026, 11, 8),
        booked_slot_count=7,
    )
    skipped = [
        {"date": "2026-10-12", "reason": "already_booked"},
        {"date": "2026-10-14", "reason": "other_case", "other_case_id": 99},
    ]
    body = _recurring_summary_body(case, None, record, skipped)
    assert "2026-10-12" not in body.split("Left off:")[-1]
    assert "2026-10-14 (that time is booked for another case)" in body
    assert "99" not in body.split("Left off:")[-1]
