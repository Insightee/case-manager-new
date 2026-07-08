"""Shared status vocabulary, source-line formatting, and banned-word guard for insights."""

from __future__ import annotations

import re
from typing import Any

GOAL_STATUS_EMERGING = "Emerging"
GOAL_STATUS_BUILDING = "Building"
GOAL_STATUS_CONSISTENT = "Consistent"
GOAL_STATUS_NEEDS_ADAPTING = "Needs adapting"
GOAL_STATUS_NOT_ENOUGH_EVIDENCE = "Not enough evidence"

STRATEGY_RESPONSE_HELPFUL = "Helpful"
STRATEGY_RESPONSE_PARTLY_HELPFUL = "Partly helpful"
STRATEGY_RESPONSE_NEEDS_ADAPTING = "Needs adapting"
STRATEGY_RESPONSE_NOT_ENOUGH_EVIDENCE = "Not enough evidence"

SUGGESTED_CASE_SPECIFIC = "Case-specific"
SUGGESTED_PENDING_CM_REVIEW = "Pending CM review"
SUGGESTED_APPROVED_STRATEGY = "Approved strategy"
SUGGESTED_POOL_CANDIDATE = "Pool candidate"
SUGGESTED_ADAPTATION = "Suggested adaptation"

BANNED_WORDS = (
    "patient",
    "compliance",
    "behavioral clustering",
    "cognitive progress analysis",
    "neural patterns",
    "goal attainment",
    "deficit",
    "non-compliant",
    "failed goal",
    "aggressive child",
)

_BANNED_PATTERN = re.compile("|".join(re.escape(w) for w in BANNED_WORDS), re.IGNORECASE)


def contains_banned_language(text: str | None) -> bool:
    """True if `text` uses any doctrine-banned clinical/medical-heavy phrase."""
    if not text:
        return False
    return bool(_BANNED_PATTERN.search(text))


def goal_status_label(evidence_strength: str | None, latest_trend: str | None, sessions_addressed: int) -> str:
    if sessions_addressed <= 0:
        return GOAL_STATUS_NOT_ENOUGH_EVIDENCE
    if latest_trend == "needs_support":
        return GOAL_STATUS_NEEDS_ADAPTING
    if evidence_strength == "weak":
        return GOAL_STATUS_NOT_ENOUGH_EVIDENCE if sessions_addressed < 2 else GOAL_STATUS_EMERGING
    if evidence_strength == "moderate":
        return GOAL_STATUS_BUILDING
    if evidence_strength == "strong_operational":
        return GOAL_STATUS_CONSISTENT if latest_trend in (None, "stable", "improving") else GOAL_STATUS_BUILDING
    return GOAL_STATUS_EMERGING


def strategy_response_label(feedback_distribution: dict[str, int] | None, use_count: int) -> str:
    dist = feedback_distribution or {}
    helpful = dist.get("HELPFUL", 0)
    partly = dist.get("PARTLY_HELPFUL", 0)
    needs = dist.get("NEEDS_ADAPTATION", 0) + dist.get("CHILD_REJECTED", 0) + dist.get("NOT_HELPFUL", 0)
    total = helpful + partly + needs
    if use_count <= 0 or total == 0:
        return STRATEGY_RESPONSE_NOT_ENOUGH_EVIDENCE
    if needs >= helpful and needs >= partly and needs > 0:
        return STRATEGY_RESPONSE_NEEDS_ADAPTING
    if helpful >= partly:
        return STRATEGY_RESPONSE_HELPFUL if helpful >= total * 0.5 else STRATEGY_RESPONSE_PARTLY_HELPFUL
    return STRATEGY_RESPONSE_PARTLY_HELPFUL


def suggested_strategy_status(repo_status: str | None, helpful_count: int, pool_threshold: int = 3) -> str:
    if helpful_count >= pool_threshold:
        return SUGGESTED_POOL_CANDIDATE
    if repo_status == "approved" or repo_status == "active":
        return SUGGESTED_APPROVED_STRATEGY
    if repo_status == "candidate":
        return SUGGESTED_PENDING_CM_REVIEW
    return SUGGESTED_CASE_SPECIFIC


def suggested_goal_status(repo_status: str | None) -> str:
    if repo_status == "candidate":
        return SUGGESTED_PENDING_CM_REVIEW
    return SUGGESTED_CASE_SPECIFIC


def source_line(label: str, count: int) -> str:
    unit = label if count == 1 else f"{label}s"
    return f"Source: {count} {unit}"


def combined_source_line(parts: list[tuple[int, str]]) -> str:
    """parts: list of (count, singular_label) — e.g. [(1, 'incident note'), (2, 'session log')]."""
    bits = [f"{count} {label if count == 1 else label + 's'}" for count, label in parts if count > 0]
    if not bits:
        return "Source: no matching records yet"
    return "Source: " + ", ".join(bits)


def make_insight(
    *,
    insight_id: str,
    insight_type: str,
    title: str,
    summary: str,
    status: str | None = None,
    source_type: str = "session_logs",
    source_count: int = 0,
    source_label: str | None = None,
    linked_goal_id: str | None = None,
    linked_strategy_id: str | None = None,
    recommended_action: str | None = None,
    review_path: str | None = None,
) -> dict[str, Any]:
    return {
        "id": insight_id,
        "type": insight_type,
        "title": title,
        "summary": summary,
        "status": status,
        "source": {
            "type": source_type,
            "count": source_count,
            "label": source_label or source_line(source_type.rstrip("s").replace("_", " "), source_count),
        },
        "linkedGoalId": linked_goal_id,
        "linkedStrategyId": linked_strategy_id,
        "recommendedAction": recommended_action,
        "reviewPath": review_path,
        "confidence": "structured_data_supported",
        "requiresAI": False,
    }
