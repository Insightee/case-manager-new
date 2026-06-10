"""Effective session times for billing after approved corrections."""

from __future__ import annotations

from datetime import date, datetime, time, timezone

from app.core.session_times import effective_session_datetimes
from app.models.daily_log import DailyLog, LogApprovalStatus
from app.models.session import Session as TherapySession
from app.models.session import SessionMode, SessionStatus
from app.services.invoice_billing_service import session_duration_minutes


def _session_and_log(*, approved: bool) -> tuple[TherapySession, DailyLog]:
    clock_start = datetime(2026, 6, 8, 9, 0, tzinfo=timezone.utc)
    clock_end = datetime(2026, 6, 8, 10, 0, tzinfo=timezone.utc)
    edited_start = datetime(2026, 6, 8, 9, 15, tzinfo=timezone.utc)
    edited_end = datetime(2026, 6, 8, 10, 30, tzinfo=timezone.utc)
    session = TherapySession(
        id=1,
        case_id=1,
        therapist_user_id=1,
        scheduled_date=date(2026, 6, 8),
        start_time=time(9, 0),
        end_time=time(10, 0),
        mode=SessionMode.HOME,
        status=SessionStatus.COMPLETED,
        actual_start_at=clock_start,
        actual_end_at=clock_end,
        edited_start_at=edited_start,
        edited_end_at=edited_end,
        actual_times_edited=True,
    )
    log = DailyLog(
        id=1,
        session_id=1,
        approval_status=LogApprovalStatus.APPROVED if approved else LogApprovalStatus.PENDING,
    )
    return session, log


def test_effective_times_use_clock_when_log_pending():
    session, log = _session_and_log(approved=False)
    start, end = effective_session_datetimes(session, log)
    assert start == session.actual_start_at
    assert end == session.actual_end_at


def test_effective_times_use_edited_when_log_approved():
    session, log = _session_and_log(approved=True)
    start, end = effective_session_datetimes(session, log)
    assert start == session.edited_start_at
    assert end == session.edited_end_at


def test_session_duration_minutes_uses_edited_after_approval():
    session, log = _session_and_log(approved=True)
    assert session_duration_minutes(session, log) == 75
