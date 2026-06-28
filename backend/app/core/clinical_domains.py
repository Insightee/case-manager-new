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

NEUROAFFIRMATIVE_AVOID = [
    "non-compliant",
    "non compliant",
    "attention-seeking",
    "attention seeking",
    "manipulative",
    "defiant",
    "poor behaviour",
    "poor behavior",
    "tantrum",
    "meltdown",
    "poor eye contact",
    "lack of eye contact",
    "autistic behaviour",
    "autistic behavior",
    "high functioning",
    "low functioning",
    "doesn't listen",
    "does not listen",
    "refuses to",
    "challenging behaviour",
    "challenging behavior",
]

COMPLIANCE_GOAL_BLOCKLIST = [
    "eye contact",
    "stop stimming",
    "sit still",
    "obey instructions",
    "behave normally",
    "reduce autistic",
    "stop tantrum",
    "make eye contact",
    "sit quietly",
    "stop flapping",
    "normal child",
]

SUGGESTED_REPLACEMENTS: dict[str, str] = {
    "non-compliant": "needs support to participate",
    "non compliant": "needs support to participate",
    "attention-seeking": "connection-seeking",
    "attention seeking": "connection-seeking",
    "manipulative": "communicating a need",
    "defiant": "resisting when overwhelmed",
    "poor behaviour": "dysregulated moment",
    "poor behavior": "dysregulated moment",
    "tantrum": "dysregulated moment",
    "meltdown": "overwhelm response",
    "poor eye contact": "variable engagement cues",
    "lack of eye contact": "variable engagement cues",
    "autistic behaviour": "neurodivergent expression",
    "autistic behavior": "neurodivergent expression",
    "eye contact": "engagement with communication partner",
    "stop stimming": "access regulation supports",
    "sit still": "sustained participation with movement breaks",
    "obey instructions": "follow agreed routines with support",
    "behave normally": "participate in expected ways with accommodations",
    "stop tantrum": "co-regulate during dysregulation",
}
