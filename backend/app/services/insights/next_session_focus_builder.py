"""Deterministic "Next Session Focus" card — 1 goal + 1 strategy + 1 observe + 1 adapt."""

from __future__ import annotations

from typing import Any

from app.services.insights.helpers import make_insight

_GOAL_PRIORITY = {
    "Not enough evidence": 0,
    "Needs adapting": 1,
    "Emerging": 2,
    "Building": 3,
    "Consistent": 4,
}
_STRATEGY_PRIORITY_FOR_ADAPT = {"Needs adapting": 0, "Not enough evidence": 1, "Partly helpful": 2, "Helpful": 3}


def build_next_session_focus(
    goal_cards: list[dict[str, Any]],
    evidence_cards: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    if not goal_cards:
        return None

    focus_goal = min(goal_cards, key=lambda g: (_GOAL_PRIORITY.get(g["status"], 2), g["sessionsAddressed"]))

    focus_strategy = None
    strategies = focus_goal.get("strategies") or []
    if strategies:
        focus_strategy = min(
            strategies,
            key=lambda s: _STRATEGY_PRIORITY_FOR_ADAPT.get(s["response"], 2),
        )

    observe = evidence_cards.get("supportConcerns", {}).get("summary") or (
        f"Observe how {focus_goal['label']} responds when support level changes."
    )
    adapt = evidence_cards.get("needsAdapting", {}).get("summary") or (
        f"Adapt pacing or supports for \"{focus_goal['label']}\" if participation drops."
    )

    strategy_line = f" Use {focus_strategy['label']}." if focus_strategy else ""
    summary = (
        f"Next session focus: Work on \"{focus_goal['label']}\".{strategy_line} "
        f"Observe: {observe[:160]}"
    )

    return {
        "goalId": focus_goal["goalId"],
        "goalLabel": focus_goal["label"],
        "strategyId": focus_strategy["strategyId"] if focus_strategy else None,
        "strategyLabel": focus_strategy["label"] if focus_strategy else None,
        "observe": observe,
        "adapt": adapt,
        "summary": summary,
    }


def next_session_focus_to_insight(focus: dict[str, Any] | None) -> dict | None:
    if not focus:
        return None
    return make_insight(
        insight_id="next_session_focus",
        insight_type="next_session",
        title="Next session focus",
        summary=focus["summary"],
        source_type="session_logs",
        source_count=0,
        source_label="Source: recent goal, strategy, and evidence patterns",
        linked_goal_id=focus["goalId"],
        linked_strategy_id=focus.get("strategyId"),
        recommended_action="Add to Next Session Plan",
        review_path="therapist_review",
    )
