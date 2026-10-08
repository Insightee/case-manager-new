"""Unit tests for shared daily-log narrative helpers."""

from __future__ import annotations

from app.models.daily_log import DailyLog
from app.services.daily_log_narrative import daily_log_has_narrative, daily_log_narrative_snippet


def test_daily_log_has_narrative():
    assert daily_log_has_narrative(
        DailyLog(session_id=1, attendance_status="PRESENT", activities_done="Built tower")
    )
    assert not daily_log_has_narrative(
        DailyLog(session_id=1, attendance_status="PRESENT", session_notes="  ", observations=None)
    )


def test_daily_log_narrative_snippet_truncates():
    long_text = "x" * 200
    log = DailyLog(session_id=1, attendance_status="PRESENT", session_notes=long_text)
    snippet = daily_log_narrative_snippet(log, limit=50)
    assert len(snippet) <= 51
    assert snippet.endswith("…")
