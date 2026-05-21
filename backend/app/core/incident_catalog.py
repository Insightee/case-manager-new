from __future__ import annotations

from typing import Any

from app.models.incident import IncidentOwnerRole, IncidentPriority, IncidentPrimaryCategory

PRIMARY_CATEGORIES: list[dict[str, str]] = [
    {"key": IncidentPrimaryCategory.CHILD_SAFETY_MEDICAL.value, "label": "Child Safety & Medical"},
    {"key": IncidentPrimaryCategory.BEHAVIOUR_EMOTIONAL.value, "label": "Behaviour & Emotional Regulation"},
    {"key": IncidentPrimaryCategory.SESSION_CLASSROOM_PROGRAM.value, "label": "Session / Classroom / Program Incident"},
    {"key": IncidentPrimaryCategory.PARENT_SCHOOL_COMMUNICATION.value, "label": "Parent / School / Communication Issue"},
    {"key": IncidentPrimaryCategory.THERAPIST_PARENT_CONDUCT.value, "label": "Therapist / Parent Conduct & Compliance"},
    {"key": IncidentPrimaryCategory.SAFEGUARDING_CONSENT_PRIVACY.value, "label": "Safeguarding, Consent & Privacy"},
    {"key": IncidentPrimaryCategory.LEGAL_POSH_CPP_POCSO.value, "label": "Legal — POSH / CPP / POCSO"},
]

SUBCATEGORIES_BY_CATEGORY: dict[str, list[dict[str, str]]] = {
    IncidentPrimaryCategory.CHILD_SAFETY_MEDICAL.value: [
        {"key": "injury_fall", "label": "Injury / fall"},
        {"key": "self_injury", "label": "Self-injury"},
        {"key": "elopement", "label": "Child ran away / unsafe movement"},
        {"key": "fever_illness", "label": "Fever / illness"},
        {"key": "seizure_breathing", "label": "Seizure / breathing issue"},
        {"key": "medical_emergency", "label": "Medical emergency"},
        {"key": "other", "label": "Other"},
    ],
    IncidentPrimaryCategory.BEHAVIOUR_EMOTIONAL.value: [
        {"key": "meltdown_shutdown", "label": "Meltdown / shutdown"},
        {"key": "aggression", "label": "Aggression"},
        {"key": "severe_refusal", "label": "Severe refusal"},
        {"key": "crying_panic", "label": "Excessive crying / panic"},
        {"key": "property_damage", "label": "Property damage"},
        {"key": "new_behaviour_concern", "label": "New or increased behaviour concern"},
        {"key": "other", "label": "Other"},
    ],
    IncidentPrimaryCategory.SESSION_CLASSROOM_PROGRAM.value: [
        {"key": "session_disrupted", "label": "Session disrupted"},
        {"key": "child_refused_session", "label": "Child refused session/activity"},
        {"key": "goal_not_completed", "label": "Goal not completed"},
        {"key": "classroom_issue", "label": "Classroom issue"},
        {"key": "peer_conflict", "label": "Peer conflict"},
        {"key": "school_access_issue", "label": "School/program access issue"},
        {"key": "other", "label": "Other"},
    ],
    IncidentPrimaryCategory.PARENT_SCHOOL_COMMUNICATION.value: [
        {"key": "parent_complaint", "label": "Parent complaint"},
        {"key": "school_complaint", "label": "School complaint"},
        {"key": "miscommunication", "label": "Miscommunication"},
        {"key": "harsh_communication", "label": "Harsh/inappropriate communication"},
        {"key": "plan_disagreement", "label": "Parent/school disagreement with plan"},
        {"key": "communication_delay", "label": "Delay in communication"},
        {"key": "other", "label": "Other"},
    ],
    IncidentPrimaryCategory.THERAPIST_PARENT_CONDUCT.value: [
        {"key": "therapist_late_noshow", "label": "Therapist late / no-show"},
        {"key": "parent_noshow", "label": "Parent no-show / unavailable"},
        {"key": "missing_session_note", "label": "Missing session note"},
        {"key": "not_following_plan", "label": "Not following plan"},
        {"key": "boundary_concern", "label": "Boundary concern"},
        {"key": "unprofessional_behaviour", "label": "Unprofessional behaviour"},
        {"key": "other", "label": "Other"},
    ],
    IncidentPrimaryCategory.SAFEGUARDING_CONSENT_PRIVACY.value: [
        {"key": "suspected_abuse", "label": "Suspected abuse / neglect"},
        {"key": "child_disclosure", "label": "Child disclosure of harm"},
        {"key": "consent_issue", "label": "Consent issue"},
        {"key": "photo_without_consent", "label": "Photo/video without consent"},
        {"key": "confidentiality_breach", "label": "Confidential information shared wrongly"},
        {"key": "serious_boundary", "label": "Serious boundary concern"},
        {"key": "other", "label": "Other"},
    ],
    IncidentPrimaryCategory.LEGAL_POSH_CPP_POCSO.value: [
        {"key": "posh_concern", "label": "POSH concern"},
        {"key": "cpp_concern", "label": "CPP concern"},
        {"key": "pocso_concern", "label": "POCSO concern"},
        {"key": "legal_notice", "label": "Legal notice / legal threat"},
        {"key": "police_involvement", "label": "Police/legal authority involvement"},
        {"key": "other_legal", "label": "Other legal concern"},
    ],
}

SERVICE_TYPES = [
    {"key": "shadow", "label": "Shadow"},
    {"key": "homecare", "label": "Homecare"},
    {"key": "counselling", "label": "Counselling"},
    {"key": "spot", "label": "SPOT"},
    {"key": "school_program", "label": "School program"},
    {"key": "other", "label": "Other"},
]

LOCATIONS = [
    {"key": "home", "label": "Home"},
    {"key": "school", "label": "School"},
    {"key": "clinic", "label": "Clinic"},
    {"key": "spot", "label": "SPOT"},
    {"key": "online", "label": "Online"},
]

PRIORITIES = [
    {"key": IncidentPriority.NORMAL.value, "label": "Normal"},
    {"key": IncidentPriority.URGENT.value, "label": "Urgent"},
    {"key": IncidentPriority.CRITICAL.value, "label": "Critical"},
]

YES_NO_NA = [
    {"key": "yes", "label": "Yes"},
    {"key": "no", "label": "No"},
    {"key": "na", "label": "Not applicable"},
]

# Subcategory key -> default priority
SUBCATEGORY_DEFAULT_PRIORITY: dict[str, str] = {
    "medical_emergency": IncidentPriority.CRITICAL.value,
    "seizure_breathing": IncidentPriority.CRITICAL.value,
    "elopement": IncidentPriority.CRITICAL.value,
    "injury_fall": IncidentPriority.URGENT.value,
    "self_injury": IncidentPriority.URGENT.value,
    "suspected_abuse": IncidentPriority.CRITICAL.value,
    "child_disclosure": IncidentPriority.CRITICAL.value,
    "pocso_concern": IncidentPriority.CRITICAL.value,
    "posh_concern": IncidentPriority.CRITICAL.value,
    "cpp_concern": IncidentPriority.CRITICAL.value,
    "police_involvement": IncidentPriority.CRITICAL.value,
    "legal_notice": IncidentPriority.CRITICAL.value,
    "parent_complaint": IncidentPriority.URGENT.value,
    "school_complaint": IncidentPriority.URGENT.value,
    "aggression": IncidentPriority.URGENT.value,
    "boundary_concern": IncidentPriority.URGENT.value,
    "unprofessional_behaviour": IncidentPriority.URGENT.value,
    "confidentiality_breach": IncidentPriority.URGENT.value,
    "serious_boundary": IncidentPriority.URGENT.value,
    "therapist_late_noshow": IncidentPriority.NORMAL.value,
    "missing_session_note": IncidentPriority.NORMAL.value,
    "session_disrupted": IncidentPriority.NORMAL.value,
    "communication_delay": IncidentPriority.NORMAL.value,
}

_THERAPIST_CONDUCT_KEYS = frozenset(
    {
        "therapist_late_noshow",
        "missing_session_note",
        "not_following_plan",
        "boundary_concern",
        "unprofessional_behaviour",
    }
)

_PARENT_CONDUCT_KEYS = frozenset({"parent_noshow"})


def validate_category_subcategory(primary_category: str, subcategory: str) -> None:
    cat = (primary_category or "").strip().upper()
    sub = (subcategory or "").strip().lower()
    if cat not in SUBCATEGORIES_BY_CATEGORY:
        raise ValueError("Invalid primary category")
    keys = {s["key"] for s in SUBCATEGORIES_BY_CATEGORY[cat]}
    if sub not in keys:
        raise ValueError("Invalid subcategory for this category")


def default_priority_for_subcategory(subcategory: str) -> str:
    return SUBCATEGORY_DEFAULT_PRIORITY.get((subcategory or "").lower(), IncidentPriority.NORMAL.value)


def route_incident(
    primary_category: str,
    subcategory: str,
    *,
    reporter_role_names: list[str] | None = None,
) -> dict[str, Any]:
    """Return primary_owner_role and tagged_roles (user IDs resolved in service)."""
    cat = (primary_category or "").strip().upper()
    sub = (subcategory or "").strip().lower()
    tagged: list[str] = []
    priority = default_priority_for_subcategory(sub)

    if cat == IncidentPrimaryCategory.LEGAL_POSH_CPP_POCSO.value:
        return {
            "primary_owner_role": IncidentOwnerRole.HR.value,
            "tagged_roles": tagged,
            "priority": priority,
        }

    if cat == IncidentPrimaryCategory.SAFEGUARDING_CONSENT_PRIVACY.value:
        tagged.append(IncidentOwnerRole.HR.value)
        return {
            "primary_owner_role": IncidentOwnerRole.CASE_MANAGER.value,
            "tagged_roles": tagged,
            "priority": priority,
        }

    if cat == IncidentPrimaryCategory.THERAPIST_PARENT_CONDUCT.value:
        if sub in _THERAPIST_CONDUCT_KEYS or "therapist" in sub or "staff" in sub:
            return {
                "primary_owner_role": IncidentOwnerRole.HR.value,
                "tagged_roles": tagged,
                "priority": priority,
            }
        if sub in _PARENT_CONDUCT_KEYS or "parent" in sub:
            return {
                "primary_owner_role": IncidentOwnerRole.CASE_MANAGER.value,
                "tagged_roles": tagged,
                "priority": priority,
            }
        # Default conduct: HR for staff-related wording in reporter roles
        roles = reporter_role_names or []
        if RoleName_THERAPIST in roles:
            return {
                "primary_owner_role": IncidentOwnerRole.HR.value,
                "tagged_roles": tagged,
                "priority": priority,
            }
        return {
            "primary_owner_role": IncidentOwnerRole.CASE_MANAGER.value,
            "tagged_roles": tagged,
            "priority": priority,
        }

    return {
        "primary_owner_role": IncidentOwnerRole.CASE_MANAGER.value,
        "tagged_roles": tagged,
        "priority": priority,
    }


RoleName_THERAPIST = "THERAPIST"


def category_label(key: str) -> str:
    for c in PRIMARY_CATEGORIES:
        if c["key"] == key:
            return c["label"]
    return key


def subcategory_label(primary_category: str, subcategory: str) -> str:
    for s in SUBCATEGORIES_BY_CATEGORY.get(primary_category, []):
        if s["key"] == subcategory:
            return s["label"]
    return subcategory


def meta_payload() -> dict:
    return {
        "primary_categories": PRIMARY_CATEGORIES,
        "subcategories_by_category": SUBCATEGORIES_BY_CATEGORY,
        "service_types": SERVICE_TYPES,
        "locations": LOCATIONS,
        "priorities": PRIORITIES,
        "yes_no_na": YES_NO_NA,
        "owner_roles": [
            {"key": IncidentOwnerRole.CASE_MANAGER.value, "label": "Case Manager"},
            {"key": IncidentOwnerRole.HR.value, "label": "HR"},
            {"key": IncidentOwnerRole.ADMIN.value, "label": "Admin"},
        ],
        "statuses": [
            {"key": "REPORTED", "label": "Reported"},
            {"key": "IN_REVIEW", "label": "In review"},
            {"key": "ACTION_TAKEN", "label": "Action taken"},
            {"key": "ESCALATED", "label": "Escalated"},
            {"key": "CLOSED", "label": "Closed"},
        ],
    }
