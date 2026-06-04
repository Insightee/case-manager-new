"""Login portal enforcement — client, therapist, and staff sign-in URLs."""

from __future__ import annotations

from typing import Literal

from app.core.permissions import RoleName
from app.models.user import User

LoginPortal = Literal["parent", "therapist", "staff"]

STAFF_LOGIN_ROLES: frozenset[str] = frozenset(
    {
        RoleName.SUPER_ADMIN.value,
        RoleName.ADMIN.value,
        RoleName.MODULE_ADMIN.value,
        RoleName.VIEWER.value,
        RoleName.CASE_MANAGER.value,
        RoleName.SUPERVISOR.value,
        RoleName.FINANCE.value,
        RoleName.HR.value,
        RoleName.SCHOOL_COORDINATOR.value,
    }
)

_PORTAL_ALLOWED_ROLES: dict[LoginPortal, frozenset[str]] = {
    "parent": frozenset({RoleName.PARENT.value}),
    "therapist": frozenset({RoleName.THERAPIST.value}),
    "staff": STAFF_LOGIN_ROLES,
}

def normalize_login_portal(portal: str | None) -> LoginPortal | None:
    if portal is None:
        return None
    key = portal.strip().lower()
    if key == "admin":
        key = "staff"
    if key in _PORTAL_ALLOWED_ROLES:
        return key  # type: ignore[return-value]
    return None


def user_may_login_on_portal(user: User, portal: LoginPortal) -> bool:
    roles = {str(r).upper() for r in (user.role_names or [])}
    allowed = _PORTAL_ALLOWED_ROLES[portal]
    return bool(roles & allowed)


PORTAL_LOGIN_REJECTION_MESSAGE = "Invalid Login. Use the correct portal."


def portal_login_rejection_message(portal: LoginPortal, user: User) -> str:
    del portal, user  # same message for all wrong-portal attempts
    return PORTAL_LOGIN_REJECTION_MESSAGE
