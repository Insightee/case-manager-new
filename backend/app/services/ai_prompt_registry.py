"""Versioned prompt templates and mock drafts for AI preview actions."""

from __future__ import annotations

from typing import Any

ALLOWED_ACTIONS = frozenset(
    {
        "monthly_summary",
        "improve_session_note",
        "draft_monthly_goal_summary",
        "draft_monthly_parent_summary",
        "suggest_iep_goal_wording",
        "suggest_strategy_adaptation",
        "strategy_suggest",
        "clinical_review_note",
        "clinical_snapshot",
        "evidence_gap_summary",
        "neuroaffirmative_rewrite",
        "iep_goal_suggest",
        "observation_summary",
        "progress_summary",
    }
)

PROMPT_VERSION = "v1"


def validate_action(action: str) -> str:
    if action not in ALLOWED_ACTIONS:
        raise ValueError(f"Unknown AI action: {action}")
    return action


def mock_draft(action: str, context: dict[str, Any]) -> str:
    child = context.get("child_name") or "the child"
    text = context.get("text") or context.get("note") or ""
    if action == "monthly_summary":
        return (
            f"This month, {child} showed meaningful progress across targeted goals. "
            "Session evidence indicates increased participation when supports were in place. "
            "Review and edit before submitting."
        )
    if action == "improve_session_note":
        return f"Session note (draft): {child} engaged with structured activities. {text[:200]}".strip()
    if action == "draft_monthly_goal_summary":
        return f"Goal progress this month for {child}: emerging skills noted across targeted domains."
    if action == "draft_monthly_parent_summary":
        return f"This month {child} participated well in sessions. We saw meaningful progress."
    if action == "suggest_iep_goal_wording":
        return f"{child} will use preferred communication strategies during structured activities."
    if action == "suggest_strategy_adaptation":
        return "Consider visual schedules and co-regulation breaks before challenging tasks."
    if action == "evidence_gap_summary":
        return "Recent sessions lack structured goal entries. Add session goal evidence before monthly compile."
    if action == "neuroaffirmative_rewrite":
        return text or f"{child} showed strengths in engagement this session."
    if action == "iep_goal_suggest":
        return f"{child} will use preferred communication strategies to express needs during structured activities."
    if action == "observation_summary":
        return f"Observation highlights strengths in connection and engagement for {child}."
    if action == "progress_summary":
        return f"Over the review period, {child} demonstrated steady growth toward IEP goals."
    if action == "strategy_suggest":
        return f"Try visual schedules and sensory breaks to support {child} during transitions."
    if action == "clinical_review_note":
        return f"Clinical review note for {child}: document strengths-first observations and next steps."
    return "Draft preview — edit before saving. (Mock AI provider)"
