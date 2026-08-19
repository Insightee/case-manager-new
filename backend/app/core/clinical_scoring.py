"""Shared 0–4 clinical measurement scales for session goal evidence."""

from __future__ import annotations

from typing import Optional

PARTICIPATION_ANCHORS: dict[int, str] = {
    0: "Not available",
    1: "Observed only",
    2: "Partial participation",
    3: "Active participation with support",
    4: "Independent / self-led participation",
}

INDEPENDENCE_ANCHORS: dict[int, str] = {
    0: "Full support",
    1: "High support",
    2: "Moderate support",
    3: "Light prompt",
    4: "No support",
}

GOAL_ACHIEVEMENT_ANCHORS: dict[int, str] = {
    0: "Not observed",
    1: "Emerging",
    2: "Attempted",
    3: "Mostly achieved",
    4: "Achieved in today's context",
}

STRATEGY_FEEDBACK_VALUES = frozenset(
    {
        "HELPFUL",
        "PARTLY_HELPFUL",
        "NOT_HELPFUL",
        "CHILD_REJECTED",
        "NEEDS_ADAPTATION",
    }
)

NEGATIVE_STRATEGY_FEEDBACK = frozenset({"NOT_HELPFUL", "CHILD_REJECTED", "NEEDS_ADAPTATION"})

SESSION_ENVIRONMENTS = frozenset({"HOME", "SCHOOL", "CENTER", "ONLINE"})


def validate_score(value: Optional[int], *, field: str) -> Optional[int]:
    if value is None:
        return None
    if not isinstance(value, int) or value < 0 or value > 4:
        raise ValueError(f"{field} must be an integer from 0 to 4")
    return value


def validate_strategy_feedback(value: Optional[str]) -> Optional[str]:
    if value is None or value == "":
        return None
    raw = value.strip().upper()
    if raw not in STRATEGY_FEEDBACK_VALUES:
        raise ValueError(f"Invalid strategy_feedback: {value}")
    return raw
