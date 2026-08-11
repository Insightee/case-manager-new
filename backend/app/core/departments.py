"""Staff department tags — orthogonal to RBAC roles."""

from __future__ import annotations

STAFF_DEPARTMENTS: tuple[dict[str, str], ...] = (
    {"id": "FINANCE", "label": "Finance"},
    {"id": "HR", "label": "HR"},
    {"id": "ONBOARDING", "label": "Onboarding"},
    {"id": "TRAINING", "label": "Training"},
    {"id": "CLIENT", "label": "Client"},
    {"id": "MARKETING", "label": "Marketing"},
    {"id": "OPERATIONS", "label": "Operations"},
    {"id": "LEADERSHIP", "label": "Leadership"},
    {"id": "TECH", "label": "Tech"},
    {"id": "MENTORS", "label": "Mentors"},
    {"id": "ONBOARDING_MENTORS", "label": "Onboarding Mentors"},
    {"id": "REVIEW_AND_COMPLIANCE", "label": "Review and Compliance"},
    {"id": "CASE_MANAGERS", "label": "Case Managers"},
)

STAFF_DEPARTMENT_IDS: frozenset[str] = frozenset(d["id"] for d in STAFF_DEPARTMENTS)

_DEPARTMENT_LABEL_BY_ID: dict[str, str] = {d["id"]: d["label"] for d in STAFF_DEPARTMENTS}


def normalize_staff_department(value: str | None) -> str | None:
    """Return canonical department id or None."""
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    upper = raw.upper().replace("-", "_").replace(" ", "_")
    if upper in STAFF_DEPARTMENT_IDS:
        return upper
    for dept_id, label in _DEPARTMENT_LABEL_BY_ID.items():
        if label.lower() == raw.lower():
            return dept_id
    return None


def validate_staff_department(value: str | None) -> str | None:
    """Validate optional department; raise ValueError if unknown."""
    if value is None:
        return None
    normalized = normalize_staff_department(value)
    if normalized is None and str(value).strip():
        allowed = ", ".join(sorted(_DEPARTMENT_LABEL_BY_ID.values()))
        raise ValueError(f"Unknown department. Choose one of: {allowed}")
    return normalized


def staff_department_label(department_id: str | None) -> str | None:
    if not department_id:
        return None
    return _DEPARTMENT_LABEL_BY_ID.get(str(department_id).upper())


def staff_departments_for_api() -> list[dict[str, str]]:
    return [{"id": d["id"], "label": d["label"]} for d in STAFF_DEPARTMENTS]
