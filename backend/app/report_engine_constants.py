"""Clinical report engine constants — section catalogs and legacy mappings."""

from __future__ import annotations

# 17 observation sections (engine source of truth)
OBSERVATION_REPORT_SECTIONS: list[dict[str, str | bool]] = [
    {"key": "child_snapshot", "label": "Child Snapshot", "required": True, "prompt": "Brief strengths-forward snapshot of the child."},
    {"key": "referral_background", "label": "Referral & Background", "required": True, "prompt": "Why support was requested and relevant background."},
    {"key": "strengths_interests", "label": "Strengths & Interests", "required": True, "prompt": "What the child enjoys and does well."},
    {"key": "communication", "label": "Communication", "required": True, "prompt": "How the child communicates and understands others."},
    {"key": "regulation_sensory", "label": "Regulation & Sensory", "required": True, "prompt": "Sensory preferences and regulation patterns."},
    {"key": "participation", "label": "Participation", "required": True, "prompt": "How the child joins activities and routines."},
    {"key": "learning_access", "label": "Learning Access", "required": True, "prompt": "Access to learning tasks and materials."},
    {"key": "peer_interaction", "label": "Social / Peer Interaction", "required": False, "prompt": "Peer relationships and group dynamics."},
    {"key": "environment_notes", "label": "Environment Notes", "required": False, "prompt": "Home, school, and community contexts."},
    {"key": "strategies_tried", "label": "Strategies Tried During Observation", "required": True, "prompt": "What was tried and how the child responded."},
    {"key": "support_needs", "label": "Support Needs", "required": True, "prompt": "Areas where support would help participation."},
    {"key": "emerging_goals", "label": "Emerging Goals", "required": False, "prompt": "Initial goal directions for IEP planning."},
    {"key": "parent_inputs", "label": "Parent Inputs", "required": False, "prompt": "Family priorities and observations."},
    {"key": "school_inputs", "label": "School Inputs", "required": False, "prompt": "School team observations if available."},
    {"key": "clinical_summary", "label": "Clinical Summary", "required": True, "prompt": "Integrated summary for case manager review."},
    {"key": "recommendations_iep", "label": "Recommendations for IEP", "required": True, "prompt": "Suggested next steps for support plan."},
    {"key": "internal_notes", "label": "Internal Notes", "required": False, "prompt": "CM-only notes — never parent-visible.", "visibility": "internal_only"},
]

LEGACY_CHECKLIST_KEY_MAP: dict[str, str] = {
    "referral_context": "referral_background",
    "classroom_setting": "environment_notes",
    "social_communication": "communication",
    "academic_learning": "learning_access",
    "behavior_regulation": "regulation_sensory",
    "motor_play": "participation",
    "summary_recommendations": "clinical_summary",
}

IEP_REPORT_SECTIONS: list[dict[str, str | bool]] = [
    {"key": "child_context", "label": "Client Profile", "required": True, "prompt": "Strengths-forward snapshot and care team context."},
    {"key": "clinical_insights", "label": "Clinical Insights", "required": False, "prompt": "Promising strategies and emerging barriers from observation."},
    {"key": "priority_domains", "label": "Present Levels", "required": True, "prompt": "Strengths and support needs by domain."},
    {"key": "strategies_accommodations", "label": "Learning Environments", "required": False, "prompt": "Environmental supports and accommodations."},
    {"key": "goals_plan", "label": "Goals Plan", "required": True, "prompt": "Active and proposed goals with measurement criteria."},
    {"key": "talent_development", "label": "Talent Development", "required": False, "prompt": "Strengths to leverage and growth opportunities."},
    {"key": "review_parent_plan", "label": "Service & Implementation Plan", "required": True, "prompt": "Service frequency, review schedule, parent inputs."},
    {"key": "internal_cm_notes", "label": "Internal CM Notes", "required": False, "prompt": "Case manager notes — never parent-visible.", "visibility": "internal_only"},
]

REPORT_TYPE_HOOKS: dict[str, dict] = {
    "observation": {"evidence_sources": ["session_logs", "checklists", "uploads"], "implemented": True},
    "iep": {"evidence_sources": ["observation_report", "goal_repository", "strategy_repository", "session_logs"], "implemented": True},
    "monthly": {"evidence_sources": ["session_logs", "iep_baseline"], "implemented": False},
    "progress": {"evidence_sources": ["monthly_reports"], "implemented": False},
    "history": {"evidence_sources": ["all_reports"], "implemented": False},
}

REQUIRED_OBSERVATION_SECTION_KEYS = [
    s["key"] for s in OBSERVATION_REPORT_SECTIONS if s.get("required")
]

REQUIRED_IEP_SECTION_KEYS = [s["key"] for s in IEP_REPORT_SECTIONS if s.get("required")]
