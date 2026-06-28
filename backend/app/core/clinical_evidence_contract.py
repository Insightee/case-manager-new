"""Clinical Evidence Event Contract — enums, governance, and version constants."""

from __future__ import annotations

CONTRACT_VERSION = "1.1.0"
CONTRACT_STATUS = "active"

# --- V1 core enums ---

PARTICIPATION_SIGNAL_VALUES = (
    "not_observed",
    "minimal",
    "partial",
    "active_with_support",
    "sustained",
    "initiated_by_child",
)

EVIDENCE_STRENGTH_VALUES = (
    "weak",
    "moderate",
    "strong",
)

THERAPIST_INTERPRETATION_VALUES = (
    "continue",
    "continue_with_adaptation",
    "try_elsewhere",
    "pause",
    "cm_review",
)

PARENT_VISIBLE_STATUSES = frozenset({"APPROVED_FOR_PARENT", "SHARED_WITH_PARENT"})

# --- V1.1 optional (schema reservation; V2 UI capture) ---

CHILD_AGENCY_SIGNAL_VALUES = (
    "not_observed",
    "accepted",
    "accepted_with_choice",
    "requested_more_time",
    "requested_break",
    "requested_help",
    "requested_change",
    "refused_or_declined",
    "showed_preference",
    "self_advocated",
    "distress_signal_observed",
)

PARTICIPATION_QUALITY_VALUES = (
    "not_observed",
    "present_but_not_engaged",
    "engaged_briefly",
    "meaningful_with_support",
    "meaningful_independent",
    "initiated_by_child",
    "shared_engagement",
    "variable",
)

ENVIRONMENT_FIT_VALUES = (
    "supportive",
    "partially_supportive",
    "barrier_present",
    "overwhelming",
    "unpredictable",
    "not_observed",
)

BARRIER_TYPE_VALUES = (
    "sensory_load",
    "communication_mismatch",
    "unclear_expectation",
    "unexpected_change",
    "peer_context",
    "adult_demand",
    "fatigue_or_health",
    "transition_pressure",
    "material_or_task_mismatch",
    "environmental_access",
    "not_observed",
    "other",
)

ADAPTATION_TYPE_VALUES = (
    "choice_added",
    "time_extended",
    "demand_reduced",
    "sensory_support_added",
    "communication_mode_changed",
    "visual_changed",
    "adult_position_changed",
    "environment_modified",
    "peer_support_added",
    "routine_adjusted",
    "not_applicable",
    "other",
)

SENSITIVITY_LEVEL_VALUES = (
    "normal",
    "sensitive_family_context",
    "sensitive_school_context",
    "safeguarding_related",
    "staff_supervision_related",
    "do_not_use_for_ai",
)

LEARNING_ELIGIBILITY_VALUES = (
    "not_eligible",
    "eligible_after_review",
    "eligible_now",
    "case_specific_only",
    "deidentified_research_candidate",
)

FIELD_PROVENANCE_VALUES = (
    "human_selected",
    "human_written",
    "system_derived",
    "ai_suggested",
    "ai_extracted",
    "cm_edited",
    "system_computed",
    "unknown",
)

RECOMMENDATION_THERAPIST_ACTION_VALUES = (
    "accepted",
    "accepted_with_adaptation",
    "dismissed_not_relevant",
    "dismissed_already_tried",
    "dismissed_child_preference",
    "dismissed_environment_not_fit",
    "needs_cm_review",
)

# Structured participation enum → contract participation_signal (safe direct map)
PARTICIPATION_ENUM_TO_SIGNAL: dict[str, str] = {
    "not_yet_participating": "minimal",
    "emerging_participation": "partial",
    "participates_with_support": "active_with_support",
    "participates_consistently": "sustained",
    "generalising_across_settings": "sustained",
}

PARTICIPATION_ENUM_TO_QUALITY: dict[str, str] = {
    "not_yet_participating": "present_but_not_engaged",
    "emerging_participation": "engaged_briefly",
    "participates_with_support": "meaningful_with_support",
    "participates_consistently": "meaningful_independent",
    "generalising_across_settings": "meaningful_independent",
}

PARTICIPATION_SCORE_TO_SIGNAL: dict[int, str] = {
    0: "not_observed",
    1: "minimal",
    2: "partial",
    3: "active_with_support",
    4: "sustained",
}

STRATEGY_FEEDBACK_TO_INTERPRETATION: dict[str, str] = {
    "HELPFUL": "continue",
    "PARTLY_HELPFUL": "continue_with_adaptation",
    "NEEDS_ADAPTATION": "continue_with_adaptation",
    "NOT_HELPFUL": "try_elsewhere",
    "CHILD_REJECTED": "pause",
}

# Session-log progress signals (UI chips — neuro-affirming, separate from legacy IEP enums)

PROGRESS_PARTICIPATION_VALUES = (
    "observed_only",
    "brief_engagement",
    "participated_with_support",
    "active_participation",
    "initiated",
    "shared_engagement",
    "not_observed",
)

PROGRESS_SUPPORT_NEEDED_VALUES = (
    "independent",
    "visual_support",
    "verbal_support",
    "gestural_support",
    "co_regulation",
    "peer_support",
    "environmental_support",
    "not_observed",
)

PROGRESS_GOAL_MOVEMENT_VALUES = (
    "new_exposure",
    "practised",
    "small_movement",
    "clear_progress",
    "maintained",
    "variable",
    "more_support_needed",
    "not_enough_evidence",
)

STRATEGY_USE_STATUS_VALUES = (
    "used_as_planned",
    "adapted_today",
    "not_used",
)

CHILD_RESPONSE_VALUES = (
    "accepted",
    "needed_more_time",
    "requested_break",
    "requested_help",
    "chose_another_option",
    "declined",
    "variable",
    "not_observed",
)

# UI environment_fit uses partly_supportive alias → contract partially_supportive
ENVIRONMENT_FIT_UI_ALIASES: dict[str, str] = {
    "partly_supportive": "partially_supportive",
}

CLINICAL_EXTENSION_CAPTURE_FIELDS = frozenset(
    {
        "child_response",
        "environment_fit",
        "therapist_interpretation",
        "participation_quality",
        "support_needed",
        "goal_movement",
        "strategy_status",
        "adaptation_type",
        "adaptation_note",
        "regulation_signal",
        "child_agency_signal",
        "barrier_type",
        "field_provenance",
    }
)


def normalize_clinical_extension(raw: dict | None) -> dict:
    """Validate and normalize extension JSON from session log UI."""
    if not raw or not isinstance(raw, dict):
        return {}
    out: dict = {}
    provenance = dict(raw.get("field_provenance") or {})
    for key, value in raw.items():
        if key == "field_provenance":
            continue
        if key not in CLINICAL_EXTENSION_CAPTURE_FIELDS:
            continue
        if key == "adaptation_type":
            if isinstance(value, list):
                out[key] = [str(v) for v in value if v]
            continue
        if key == "barrier_type":
            if isinstance(value, list):
                out[key] = [str(v) for v in value if v]
            continue
        if value is not None and value != "":
            if key == "environment_fit" and isinstance(value, str):
                out[key] = ENVIRONMENT_FIT_UI_ALIASES.get(value, value)
            else:
                out[key] = value
            if key not in provenance:
                provenance[key] = "human_written" if key == "adaptation_note" else "human_selected"
    if provenance:
        out["field_provenance"] = provenance
    return out
