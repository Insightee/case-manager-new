"""Shared session-log narrative detection for reports and evidence surfaces."""

from __future__ import annotations

from sqlalchemy import func, or_

from app.models.daily_log import DailyLog

# Fields therapists use for session narrative (matches evidence-summary SQL counts).
NARRATIVE_TEXT_FIELDS: tuple[str, ...] = (
    "observations",
    "session_notes",
    "activities_done",
    "goals_addressed",
)


def iter_narrative_text_values(log: DailyLog):
    for name in NARRATIVE_TEXT_FIELDS:
        yield getattr(log, name, None)


def daily_log_has_narrative(log: DailyLog) -> bool:
    for field in iter_narrative_text_values(log):
        if field and str(field).strip():
            return True
    return False


def daily_log_narrative_snippet(log: DailyLog, limit: int = 120) -> str:
    for field in iter_narrative_text_values(log):
        text = (field or "").strip()
        if text:
            return text if len(text) <= limit else f"{text[:limit].rstrip()}…"
    return ""


def daily_log_has_nonempty_narrative_column() -> or_:
    """SQLAlchemy OR filter: any narrative column has non-whitespace text."""
    clauses = []
    for name in NARRATIVE_TEXT_FIELDS:
        col = getattr(DailyLog, name)
        clauses.append(func.length(func.trim(func.coalesce(col, ""))) > 0)
    return or_(*clauses)
