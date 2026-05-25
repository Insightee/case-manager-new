"""Shared clinical workflow constants (observation checklist sections)."""

OBSERVATION_CHECKLIST_SECTIONS: list[dict[str, str]] = [
    {"key": "referral_context", "label": "Referral & background"},
    {"key": "classroom_setting", "label": "Classroom & setting"},
    {"key": "social_communication", "label": "Social & communication"},
    {"key": "academic_learning", "label": "Academic & learning"},
    {"key": "behavior_regulation", "label": "Behavior & regulation"},
    {"key": "motor_play", "label": "Motor & play skills"},
    {"key": "summary_recommendations", "label": "Summary & recommendations"},
]
