"""Human-readable labels for support ticket raisers and assignees."""
from __future__ import annotations

from app.core.permissions import RoleName
from app.models.user import User

_ROLE_LABELS: dict[str, str] = {
    RoleName.PARENT.value: "Client / parent",
    RoleName.THERAPIST.value: "Therapist",
    RoleName.HR.value: "HR",
    RoleName.FINANCE.value: "Finance",
    RoleName.CASE_MANAGER.value: "Case manager",
    RoleName.SUPERVISOR.value: "Case manager",
    RoleName.MODULE_ADMIN.value: "Module admin",
    RoleName.ADMIN.value: "Admin",
    RoleName.SUPER_ADMIN.value: "Super admin",
    RoleName.SCHOOL_COORDINATOR.value: "School coordinator",
}

_PORTAL_PRIORITY = [
    RoleName.PARENT.value,
    RoleName.THERAPIST.value,
    RoleName.SCHOOL_COORDINATOR.value,
    RoleName.HR.value,
    RoleName.FINANCE.value,
    RoleName.CASE_MANAGER.value,
    RoleName.SUPERVISOR.value,
    RoleName.MODULE_ADMIN.value,
    RoleName.SUPER_ADMIN.value,
    RoleName.ADMIN.value,
]

ESCALATION_TARGET_ROLES: list[tuple[str, str]] = [
    (RoleName.SUPER_ADMIN.value, "Super admin"),
    (RoleName.MODULE_ADMIN.value, "Module admin"),
    (RoleName.ADMIN.value, "Admin (legacy)"),
    (RoleName.HR.value, "HR"),
    (RoleName.FINANCE.value, "Finance"),
    (RoleName.CASE_MANAGER.value, "Case manager"),
    (RoleName.SUPERVISOR.value, "Case manager (supervisor)"),
]


def role_label(role: str) -> str:
    return _ROLE_LABELS.get(role, role.replace("_", " ").title())


def role_labels(roles: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for r in roles:
        label = role_label(r)
        if label not in seen:
            seen.add(label)
            out.append(label)
    return out


def primary_portal_label(roles: list[str]) -> str:
    role_set = set(roles or [])
    for key in _PORTAL_PRIORITY:
        if key in role_set:
            return role_label(key)
    return "User"


def user_summary(user: User | None) -> dict | None:
    if not user:
        return None
    roles = list(user.role_names)
    return {
        "id": user.id,
        "full_name": user.full_name,
        "email": user.email,
        "roles": roles,
        "role_labels": role_labels(roles),
        "portal_label": primary_portal_label(roles),
    }
