"""Unit tests for HR session discrepancy rules."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from app.models.session import SessionStatus
from app.services.session_discrepancy_rules import (
    MIN_COMPLIANCE_MINUTES,
    clock_outside_padded_schedule,
    evaluate_session_anomalies,
    on_time_early_checkout_exception,
    scheduled_window_ist,
)

IST = ZoneInfo("Asia/Kolkata")


def _session(
    *,
    scheduled_date: date,
    start: time,
    end: time,
    actual_start: datetime,
    actual_end: datetime,
    status=SessionStatus.COMPLETED,
    auto_ended=False,
):
    return SimpleNamespace(
        scheduled_date=scheduled_date,
        start_time=start,
        end_time=end,
        actual_start_at=actual_start,
        actual_end_at=actual_end,
        status=status,
        auto_ended=auto_ended,
    )


def test_shadow_5pm_after_4pm_scheduled_flags_outside_and_forgot():
    d = date(2026, 9, 26)
    session = _session(
        scheduled_date=d,
        start=time(8, 0),
        end=time(16, 0),
        actual_start=datetime(2026, 9, 26, 17, 0, tzinfo=IST),
        actual_end=datetime(2026, 9, 26, 17, 5, tzinfo=IST),
    )
    assert clock_outside_padded_schedule(session, None) is True
    case = SimpleNamespace(product_module="shadow_support")
    result = evaluate_session_anomalies(session, None, case)
    assert "CLOCK_OUTSIDE_SCHEDULE" in result.codes
    assert "USE_FORGOT_TO_LOG_INSTEAD" in result.codes
    assert "DURATION_UNDER_40_MIN" in result.codes


def test_on_time_early_checkout_four_hours_not_outside():
    d = date(2026, 9, 26)
    session = _session(
        scheduled_date=d,
        start=time(8, 0),
        end=time(16, 0),
        actual_start=datetime(2026, 9, 26, 8, 0, tzinfo=IST),
        actual_end=datetime(2026, 9, 26, 12, 0, tzinfo=IST),
    )
    window = scheduled_window_ist(session)
    assert window is not None
    duration = 240
    assert on_time_early_checkout_exception(session, None, window, duration) is True
    assert clock_outside_padded_schedule(session, None) is False
    result = evaluate_session_anomalies(session, None, SimpleNamespace(product_module="shadow_support"))
    assert "CLOCK_OUTSIDE_SCHEDULE" not in result.codes


def test_missing_log_vs_pending_approval():
    d = date(2026, 9, 26)
    session = _session(
        scheduled_date=d,
        start=time(10, 0),
        end=time(11, 0),
        actual_start=datetime(2026, 9, 26, 10, 0, tzinfo=IST),
        actual_end=datetime(2026, 9, 26, 11, 0, tzinfo=IST),
    )
    no_log = evaluate_session_anomalies(session, None, SimpleNamespace(product_module="homecare"))
    assert "MISSING_LOG" in no_log.codes

    pending_log = SimpleNamespace(
        submitted_at=datetime.now(timezone.utc),
        approval_status="PENDING",
        late_addition=False,
    )
    with_log = evaluate_session_anomalies(session, pending_log, SimpleNamespace(product_module="homecare"))
    assert "MISSING_LOG" not in with_log.codes


def test_duration_under_40_for_short_completed():
    d = date(2026, 9, 26)
    session = _session(
        scheduled_date=d,
        start=time(10, 0),
        end=time(11, 0),
        actual_start=datetime(2026, 9, 26, 10, 0, tzinfo=IST),
        actual_end=datetime(2026, 9, 26, 10, 30, tzinfo=IST),
    )
    result = evaluate_session_anomalies(session, None, SimpleNamespace(product_module="homecare"))
    assert "DURATION_UNDER_40_MIN" in result.codes
    assert MIN_COMPLIANCE_MINUTES == 40
