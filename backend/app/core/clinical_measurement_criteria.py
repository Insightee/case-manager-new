"""Unified clinical measurement enums — IEP, session logs, monthly/progress reports."""

from __future__ import annotations

PARTICIPATION_VALUES: tuple[str, ...] = (
    "not_yet_participating",
    "emerging_participation",
    "participates_with_support",
    "participates_consistently",
    "generalising_across_settings",
)

INDEPENDENCE_VALUES: tuple[str, ...] = (
    "full_adult_support",
    "frequent_support",
    "moderate_support",
    "minimal_support",
    "independent_self_initiated",
)

GOAL_ACHIEVEMENT_VALUES: tuple[str, ...] = (
    "baseline",
    "emerging",
    "progressing",
    "achieved_familiar_setting",
    "achieved_across_settings",
)

GOAL_LIFECYCLE_STATUSES: tuple[str, ...] = (
    "draft",
    "pending_review",
    "active",
    "achieved",
    "revised",
    "closed",
)

MEASUREMENT_FIELDS = ("participation", "independence_support_needed", "goal_achievement")

FIELD_ALLOWED: dict[str, tuple[str, ...]] = {
    "participation": PARTICIPATION_VALUES,
    "independence_support_needed": INDEPENDENCE_VALUES,
    "goal_achievement": GOAL_ACHIEVEMENT_VALUES,
}

PARTICIPATION_LABELS: dict[str, str] = {
    "not_yet_participating": "Not yet participating",
    "emerging_participation": "Emerging participation",
    "participates_with_support": "Participates with support",
    "participates_consistently": "Participates consistently",
    "generalising_across_settings": "Generalising across settings",
}

INDEPENDENCE_LABELS: dict[str, str] = {
    "full_adult_support": "Full adult support",
    "frequent_support": "Frequent support",
    "moderate_support": "Moderate support",
    "minimal_support": "Minimal support",
    "independent_self_initiated": "Independent / self-initiated",
}

GOAL_ACHIEVEMENT_LABELS: dict[str, str] = {
    "baseline": "Baseline",
    "emerging": "Emerging",
    "progressing": "Progressing",
    "achieved_familiar_setting": "Achieved in familiar setting",
    "achieved_across_settings": "Achieved across settings",
}

FIELD_LABELS: dict[str, dict[str, str]] = {
    "participation": PARTICIPATION_LABELS,
    "independence_support_needed": INDEPENDENCE_LABELS,
    "goal_achievement": GOAL_ACHIEVEMENT_LABELS,
}

# Legacy 0–4 session log scores → enum band (index maps to enum order)
_SCORE_BANDS: dict[str, tuple[str, ...]] = {
    "participation": PARTICIPATION_VALUES,
    "independence_support_needed": INDEPENDENCE_VALUES,
    "goal_achievement": GOAL_ACHIEVEMENT_VALUES,
}


def legacy_score_to_enum(dimension: str, score: int | None) -> str | None:
    if score is None:
        return None
    bands = _SCORE_BANDS.get(dimension)
    if not bands:
        return None
    idx = max(0, min(int(score), len(bands) - 1))
    return bands[idx]


def validate_measurement_value(field: str, value: str | None) -> bool:
    if value is None or value == "":
        return False
    allowed = FIELD_ALLOWED.get(field)
    return bool(allowed and value in allowed)


def validate_measurement_fields(data: dict) -> list[str]:
    errors: list[str] = []
    for field in MEASUREMENT_FIELDS:
        val = data.get(field)
        if not validate_measurement_value(field, val):
            errors.append(field)
    return errors


def validate_iep_goal(goal: dict) -> list[str]:
    errors: list[str] = []
    if not (goal.get("title") or goal.get("goal_statement") or "").strip():
        errors.append("goal_statement")
    if not (goal.get("domain") or "").strip():
        errors.append("domain")
    if not (goal.get("baseline_current_state") or "").strip():
        errors.append("baseline_current_state")
    if not (goal.get("desired_state") or "").strip():
        errors.append("desired_state")
    errors.extend(validate_measurement_fields(goal))
    return errors
