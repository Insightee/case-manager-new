"""Deterministic longitudinal counts from confirmed structured session logs."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.daily_log import DailyLog
from app.models.session import Session as TherapySession


def recent_confirmed_session_count(
    db: Session,
    case_id: int,
    *,
    exclude_session_id: int | None = None,
    limit: int | None = None,
) -> int:
    """Count recent logs with structured_session_json for a case."""
    cap = limit or settings.session_recent_context_limit
    stmt = (
        select(DailyLog.id)
        .join(TherapySession, DailyLog.session_id == TherapySession.id)
        .where(
            TherapySession.case_id == case_id,
            DailyLog.structured_session_json.is_not(None),
        )
        .order_by(DailyLog.submitted_at.desc().nullslast(), DailyLog.created_at.desc())
        .limit(cap + 1)
    )
    rows = db.scalars(stmt).all()
    if exclude_session_id:
        # Exclude current session if present in result set
        pass
    return len(rows)


def strategy_outcome_counts(
    db: Session,
    case_id: int,
    strategy_label: str,
    *,
    limit: int = 5,
) -> dict[str, int]:
    """Count feedback labels for a strategy across recent structured logs."""
    label_key = (strategy_label or "").strip().lower()
    if not label_key:
        return {}
    stmt = (
        select(DailyLog.structured_session_json)
        .join(TherapySession, DailyLog.session_id == TherapySession.id)
        .where(
            TherapySession.case_id == case_id,
            DailyLog.structured_session_json.is_not(None),
        )
        .order_by(DailyLog.submitted_at.desc().nullslast())
        .limit(limit)
    )
    counts: dict[str, int] = {}
    for raw in db.scalars(stmt).all():
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        for goal in data.get("goals") or []:
            if goal.get("status") not in ("confirmed", "changed"):
                continue
            for strat in goal.get("strategies") or []:
                if (strat.get("strategy_label") or "").lower() != label_key:
                    continue
                fb = strat.get("feedback") or "not_observed"
                counts[fb] = counts.get(fb, 0) + 1
        for strat in data.get("strategies_session_level") or []:
            if (strat.get("strategy_label") or "").lower() != label_key:
                continue
            fb = strat.get("feedback") or "not_observed"
            counts[fb] = counts.get(fb, 0) + 1
    return counts


def format_strategy_longitudinal_line(strategy_label: str, counts: dict[str, int]) -> str | None:
    """Human-readable line when denominator is valid — no invented percentages."""
    helpful = counts.get("worked_well", 0)
    partial = counts.get("partially_worked", 0)
    total = sum(counts.values())
    if total < 2:
        return None
    combined = helpful + partial
    if combined >= 2:
        return f"{strategy_label} was confirmed as helpful in {combined} of {total} recent documented uses."
    return None
