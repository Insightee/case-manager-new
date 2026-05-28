"""Parent session log card fields match therapist template without duplication."""

from app.models.daily_log import DailyLog
from app.services import parent_home_service


def test_headline_is_attendance_not_note_text():
    log = DailyLog(
        attendance_status="PRESENT",
        parent_notes="Aarav participated well in today's session.",
        activities_done="Sensory integration and communication drills.",
    )
    headline = parent_home_service._headline_from_log(log, "Aarav M.")
    assert "participated" not in headline.lower()
    assert "Attended" in headline
    assert "Aarav" in headline


def test_summary_prefers_family_update_only():
    log = DailyLog(
        parent_notes="Family update here.",
        activities_done="Should not appear in summary when parent_notes set.",
        follow_ups="Homework practice",
    )
    summary = parent_home_service._summary_paragraph(log)
    assert summary == "Family update here."
    assert "Should not appear" not in (summary or "")
