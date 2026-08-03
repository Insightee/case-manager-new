"""Deterministic progress goal status rules — Layer 1 only."""

from __future__ import annotations

from app.services.insights.helpers import (
    GOAL_STATUS_BUILDING,
    GOAL_STATUS_CONSISTENT,
    GOAL_STATUS_EMERGING,
    GOAL_STATUS_NEEDS_ADAPTING,
    GOAL_STATUS_NOT_ENOUGH_EVIDENCE,
    goal_status_label,
    strategy_response_label,
)

VALID_FINAL_STATUSES = frozenset({
    GOAL_STATUS_EMERGING,
    GOAL_STATUS_BUILDING,
    GOAL_STATUS_CONSISTENT,
    GOAL_STATUS_NEEDS_ADAPTING,
    GOAL_STATUS_NOT_ENOUGH_EVIDENCE,
})


def suggest_goal_status(metrics: dict) -> str:
    """Map scoped goal metrics to a neuro-affirmative status label."""
    return goal_status_label(
        metrics.get("evidence_strength"),
        metrics.get("latest_trend"),
        int(metrics.get("sessions_addressed") or 0),
    )


def suggest_strategy_status(metrics: dict) -> str:
    return strategy_response_label(
        metrics.get("feedback_distribution"),
        int(metrics.get("use_count") or 0),
    )


def build_suggested_summary(metrics: dict) -> str:
    sessions = int(metrics.get("sessions_addressed") or 0)
    strategies = metrics.get("strategies_used") or []
    status = suggest_goal_status(metrics)
    parts = [f"{sessions} approved session(s) in review period."]
    if strategies:
        parts.append(f"Strategies noted: {', '.join(strategies[:5])}.")
    parts.append(f"Suggested status: {status}.")
    return " ".join(parts)


def normalize_final_status(status: str | None) -> str | None:
    if not status or not str(status).strip():
        return None
    cleaned = str(status).strip()
    for valid in VALID_FINAL_STATUSES:
        if cleaned.lower() == valid.lower():
            return valid
    raise ValueError(f"Invalid progress status: {status}")


def effective_goal_status(goal: dict) -> str:
    if goal.get("final_status"):
        return str(goal["final_status"])
    if goal.get("status_confirmed") and goal.get("suggested_status"):
        return str(goal["suggested_status"])
    return str(goal.get("suggested_status") or goal.get("status") or GOAL_STATUS_NOT_ENOUGH_EVIDENCE)


def goal_ready_for_submit(goal: dict) -> bool:
    if goal.get("final_status"):
        return True
    return bool(goal.get("status_confirmed") and goal.get("suggested_status"))
