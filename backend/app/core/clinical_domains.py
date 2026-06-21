"""13 clinical domains — shared constants for observation, IEP, and reporting."""

CLINICAL_DOMAINS = [
    {"id": "strengths_interests", "label": "Strengths & Interests"},
    {"id": "autonomy_decision", "label": "Autonomy & Decision-Making"},
    {"id": "classroom_engagement", "label": "Classroom Engagement & Participation"},
    {"id": "peer_social", "label": "Peer Interactions & Social Connection"},
    {"id": "independence", "label": "Independence"},
    {"id": "communication_aac", "label": "Communication / AAC / Alternatives"},
    {"id": "emotional_regulation", "label": "Emotional Regulation & Coping"},
    {"id": "sense_of_self", "label": "Sense of Self / Confidence"},
    {"id": "academics_learning", "label": "Academics / Learning Engagement"},
    {"id": "environment_supports", "label": "Environment Supports"},
    {"id": "parent_inputs", "label": "Parent Inputs"},
    {"id": "school_inputs", "label": "School Inputs"},
    {"id": "therapist_notes", "label": "Therapist/Internal Notes", "internal_only": True},
]

OBSERVATION_KEY_TO_DOMAIN = {
    "referral_context": "strengths_interests",
    "classroom_setting": "environment_supports",
    "social_communication": "peer_social",
    "academic_learning": "academics_learning",
    "behavior_regulation": "emotional_regulation",
    "motor_play": "independence",
    "summary_recommendations": "therapist_notes",
}
