"""Staff attendance eligibility and HR access helpers."""

from __future__ import annotations

from fastapi import HTTPException, status

from app.core.permissions import RoleName
from app.models.user import EmploymentStatus, User
from app.services.portal_login_service import STAFF_LOGIN_ROLES


def user_role_names(user: User) -> set[str]:
    return {str(r).upper() for r in (user.role_names or [])}


def is_staff_portal_user(user: User) -> bool:
    roles = user_role_names(user)
    return bool(roles & STAFF_LOGIN_ROLES)


def is_therapist_only(user: User) -> bool:
    roles = user_role_names(user)
    return RoleName.THERAPIST.value in roles and not bool(roles & STAFF_LOGIN_ROLES)


def can_manage_staff_attendance(user: User) -> bool:
    roles = user_role_names(user)
    return RoleName.SUPER_ADMIN.value in roles or RoleName.HR.value in roles


def assert_staff_attendance_eligible(user: User) -> None:
    if is_therapist_only(user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Therapists use session logs for attendance.")
    if not is_staff_portal_user(user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Staff attendance is not available for this account.")
    if user.is_view_only:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="View-only accounts cannot record attendance.",
        )
    if user.employment_status != EmploymentStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Looks like this account is not active for attendance yet.",
        )


def assert_can_view_user_attendance(actor: User, target_user_id: int) -> None:
    if actor.id == target_user_id:
        assert_staff_attendance_eligible(actor)
        return
    if not can_manage_staff_attendance(actor):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to view this attendance record.")
