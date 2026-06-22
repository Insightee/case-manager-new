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

CORE_DOMAINS = [
    {"id": "communication", "label": "Communication"},
    {"id": "social_participation", "label": "Social Participation"},
    {"id": "emotional_regulation", "label": "Emotional Regulation"},
    {"id": "sensory_regulation", "label": "Sensory Regulation"},
    {"id": "independence_daily_living", "label": "Independence / Daily Living"},
    {"id": "learning_readiness", "label": "Learning Readiness"},
    {"id": "play_engagement", "label": "Play and Engagement"},
    {"id": "motor_movement_participation", "label": "Motor / Movement Participation"},
]

CORE_ENVIRONMENTS = [
    {"id": "home", "label": "Home", "short": "Home"},
    {"id": "school_classroom", "label": "School / Classroom", "short": "School"},
    {"id": "playground", "label": "Playground", "short": "Playground"},
    {"id": "peer_interaction", "label": "Peer Interaction", "short": "Peers"},
    {"id": "community_outing", "label": "Community Outing", "short": "Community"},
    {"id": "transitions", "label": "Transitions", "short": "Transitions"},
    {"id": "interests", "label": "Interests", "short": "Interests"},
    {"id": "meal_self_care_routine", "label": "Meal / Self-care Routine", "short": "Self care"},
]
