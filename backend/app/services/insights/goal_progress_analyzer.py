"""Per-goal progress cards for the Insights tab — reuses goal_evidence_aggregation_service."""

from __future__ import annotations

import hashlib
from typing import Any

from sqlalchemy.orm import Session

from app.services import goal_evidence_aggregation_service as evidence_svc
from app.services.insights.helpers import goal_status_label, make_insight, source_line

RECENT_SESSION_WINDOW = 5


def stable_label_id(prefix: str, label: str) -> str:
    digest = hashlib.sha1(label.strip().lower().encode()).hexdigest()[:10]
    return f"{prefix}_{digest}"


def _next_step(status: str, label: str) -> str:
    if status == "Not enough evidence":
        return f"Add a session goal entry for \"{label}\" next session to build evidence."
    if status == "Needs adapting":
        return f"Review the current approach for \"{label}\" — recent entries suggest it needs adapting."
    if status == "Consistent":
        return f"Continue the current approach for \"{label}\" and capture one more session log."
    return f"Keep addressing \"{label}\" in upcoming sessions to strengthen evidence."


def build_goal_progress_cards(db: Session, case_id: int) -> list[dict[str, Any]]:
    """Returns (goal_cards, insight_objects) for every IEP goal with structured evidence."""
    summary = evidence_svc.build_goals_evidence_summary(db, case_id)
    cards: list[dict[str, Any]] = []
    for g in summary.get("goals", []):
        label = g.get("label") or "Goal"
        sessions_addressed = g.get("sessions_addressed") or 0
        status = goal_status_label(g.get("evidence_strength"), g.get("latest_trend"), sessions_addressed)
        goal_id = f"goal_{g.get('goal_id')}" if g.get("goal_id") else stable_label_id("goal_label", label)
        environments = g.get("environments") or []
        support_pattern = ", ".join(g.get("support_level_pattern") or []) or None
        measurement_bits = [f"Addressed in {sessions_addressed}/{RECENT_SESSION_WINDOW} recent sessions"]
        if support_pattern:
            measurement_bits.append(f"{support_pattern.lower()} prompting")
        if environments:
            measurement_bits.append(" and ".join(environments))
        cards.append(
            {
                "goalId": goal_id,
                "label": label,
                "domainKey": g.get("domain_key"),
                "status": status,
                "sessionsAddressed": sessions_addressed,
                "totalRecentSessions": RECENT_SESSION_WINDOW,
                "supportLevelPattern": support_pattern,
                "environments": environments,
                "measurement": " · ".join(measurement_bits),
                "progressInsight": _progress_insight(label, status, sessions_addressed),
                "evidenceSourceLine": source_line("session log", sessions_addressed),
                "nextStep": _next_step(status, label),
                "strategies": [],
            }
        )
    return cards


def _progress_insight(label: str, status: str, sessions_addressed: int) -> str:
    if status == "Not enough evidence":
        return f"Not enough session evidence yet for \"{label}\". Add goal entries in upcoming logs."
    if status == "Needs adapting":
        return f"Recent sessions suggest the current approach for \"{label}\" needs adapting."
    if status == "Consistent":
        return f"\"{label}\" shows a consistent support pattern across {sessions_addressed} recent sessions."
    if status == "Building":
        return f"\"{label}\" is building with growing evidence across {sessions_addressed} recent sessions."
    return f"\"{label}\" is emerging — early signals from {sessions_addressed} recent session(s)."


def goal_card_to_insight(card: dict[str, Any]) -> dict[str, Any]:
    return make_insight(
        insight_id=f"{card['goalId']}_progress",
        insight_type="goal_progress",
        title=card["label"],
        summary=card["progressInsight"],
        status=card["status"],
        source_type="session_logs",
        source_count=card["sessionsAddressed"],
        linked_goal_id=card["goalId"],
        recommended_action="Add Goal Insight to Monthly Report",
        review_path="cm_review" if card["status"] == "Consistent" else "therapist_review",
    )
