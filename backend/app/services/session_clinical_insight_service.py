"""Session-scoped Clinical Brain insights — deterministic Layer 1-2 only."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.feature_flags import clinical_language_engine_active
from app.services.session_longitudinal_aggregator import (
    format_strategy_longitudinal_line,
    recent_confirmed_session_count,
    strategy_outcome_counts,
)

CERTAINTY_SINGLE = "single_session_signal"
CERTAINTY_INSUFFICIENT = "insufficient_evidence"
CERTAINTY_REPEATED = "repeated_pattern"


def _confirmed_goals(structured: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        g
        for g in structured.get("goals") or []
        if g.get("status") in ("confirmed", "changed")
    ]


def _collect_strategies(structured: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for goal in structured.get("goals") or []:
        for strat in goal.get("strategies") or []:
            rows.append({**strat, "_goal_label": goal.get("goal_label")})
    for strat in structured.get("strategies_session_level") or []:
        rows.append(strat)
    return rows


def build_session_clinical_insights(
    db: Session,
    *,
    case_id: int,
    session_id: int | None,
    structured: dict[str, Any],
    extraction_insights: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Insights from confirmed evidence + longitudinal counts — never raw transcript paraphrase."""
    if not clinical_language_engine_active() and not settings.enable_clinical_brain_insights:
        return list(extraction_insights or [])

    insights: list[dict[str, Any]] = []
    confirmed = _confirmed_goals(structured)
    strategies = _collect_strategies(structured)

    for strat in strategies:
        if strat.get("feedback") != "worked_well":
            continue
        label = strat.get("strategy_label") or ""
        if label:
            insights.append(
                {
                    "insight_type": "learned_today",
                    "title": "Support noted today",
                    "summary": f"{label} appeared helpful in this session.",
                    "certainty": CERTAINTY_SINGLE,
                }
            )
            break

    recent_count = recent_confirmed_session_count(db, case_id, exclude_session_id=session_id)
    min_sessions = max(1, settings.session_insight_min_confirmed_sessions)
    if recent_count < min_sessions:
        insights.append(
            {
                "insight_type": "limitation",
                "title": "Evidence scope",
                "summary": (
                    f"Longitudinal comparison needs more confirmed sessions "
                    f"({recent_count} structured log{'s' if recent_count != 1 else ''} on file)."
                ),
                "certainty": CERTAINTY_INSUFFICIENT,
            }
        )
    else:
        for strat in strategies[:3]:
            label = strat.get("strategy_label") or ""
            if not label:
                continue
            counts = strategy_outcome_counts(db, case_id, label)
            line = format_strategy_longitudinal_line(label, counts)
            if line:
                insights.append(
                    {
                        "insight_type": "recent_comparison",
                        "title": "Recent pattern",
                        "summary": line,
                        "certainty": CERTAINTY_REPEATED,
                    }
                )
                break

    if not confirmed:
        insights.append(
            {
                "insight_type": "next_evidence",
                "title": "Next evidence opportunity",
                "summary": "Confirm which IEP goals were addressed today to strengthen this session record.",
                "certainty": CERTAINTY_INSUFFICIENT,
            }
        )

    for item in extraction_insights or []:
        if item.get("insight_type") == "limitation":
            insights.append(item)
            break

    return insights[:8]
