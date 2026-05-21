from __future__ import annotations

from enum import Enum

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.core.module_access import case_product_module_allowed
from app.models.assignment import CaseAssignment, CaseAssignmentStatus
from app.models.case import Case
from app.models.user import User


class RoleName(str, Enum):
    SUPER_ADMIN = "SUPER_ADMIN"
    ADMIN = "ADMIN"
    VIEWER = "VIEWER"
    CASE_MANAGER = "CASE_MANAGER"
    SUPERVISOR = "SUPERVISOR"
    THERAPIST = "THERAPIST"
    FINANCE = "FINANCE"
    HR = "HR"
    PARENT = "PARENT"
    SCHOOL_COORDINATOR = "SCHOOL_COORDINATOR"


ALL_PERMISSIONS = [
    "case.read.all",
    "case.read.assigned",
    "case.read.team",
    "case.read.scoped",
    "case.create",
    "case.update",
    "case.assign",
    "session.read",
    "session.create",
    "session.update",
    "daily_log.create",
    "daily_log.review",
    "monthly_report.create",
    "monthly_report.approve",
    "invoice.generate",
    "invoice.approve",
    "payout.override",
    "incident.read_sensitive",
    "admin.override",
    "user.manage",
    "parent.read",
    "ticket.manage",
    "attachment.manage",
    "leave.manage",
    "therapist.read",
    "memo.send",
    "slot.read",
    "slot.book",
    "slot.book_any",
    "slot.book_parent",
    "iep.read",
    "admin.view_only",
]

ROLE_PERMISSIONS: dict[str, list[str]] = {
    RoleName.SUPER_ADMIN: ALL_PERMISSIONS,
    RoleName.ADMIN: [
        "case.read.all",
        "case.read.scoped",
        "case.create",
        "case.update",
        "case.assign",
        "therapist.read",
        "session.read",
        "daily_log.review",
        "monthly_report.approve",
        "invoice.approve",
        "ticket.manage",
        "incident.read_sensitive",
        "parent.read",
        "slot.read",
        "slot.book_any",
    ],
    RoleName.CASE_MANAGER: [
        "case.read.team",
        "case.read.all",
        "case.create",
        "case.update",
        "case.assign",
        "therapist.read",
        "session.read",
        "session.create",
        "daily_log.review",
        "monthly_report.approve",
        "invoice.approve",
        "attachment.manage",
        "ticket.manage",
        "slot.read",
        "slot.book_any",
    ],
    RoleName.VIEWER: [
        "case.read.scoped",
        "session.read",
        "therapist.read",
        "parent.read",
        "iep.read",
        "admin.view_only",
    ],
    RoleName.SUPERVISOR: [
        "case.read.team",
        "session.read",
        "daily_log.review",
        "monthly_report.approve",
        "incident.read_sensitive",
        "iep.read",
    ],
    RoleName.THERAPIST: [
        "case.read.assigned",
        "session.read",
        "session.create",
        "session.update",
        "daily_log.create",
        "monthly_report.create",
        "invoice.generate",
        "slot.book",
    ],
    RoleName.FINANCE: [
        "case.read.all",
        "session.read",
        "invoice.approve",
        "invoice.generate",
        "payout.override",
        "ticket.manage",
        "memo.send",
    ],
    RoleName.HR: [
        "case.read.all",
        "session.read",
        "therapist.read",
        "leave.manage",
        "memo.send",
        "ticket.manage",
        "attachment.manage",
        "slot.read",
        "user.manage",
    ],
    RoleName.PARENT: ["parent.read", "slot.book_parent"],
    RoleName.SCHOOL_COORDINATOR: ["case.read.scoped", "session.read"],
}


def user_has_permission(user: User, permission: str) -> bool:
    if "admin.override" in user.permission_names:
        return True
    return permission in user.permission_names


def require_permission(permission: str):
    from app.api.deps import get_current_user

    def checker(user: User = Depends(get_current_user)) -> User:
        if not user_has_permission(user, permission):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return user

    return checker


def get_active_assignment(db: Session, case_id: int, therapist_user_id: int) -> CaseAssignment | None:
    stmt = (
        select(CaseAssignment)
        .where(
            CaseAssignment.case_id == case_id,
            CaseAssignment.therapist_user_id == therapist_user_id,
            CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
        )
        .limit(1)
    )
    return db.scalars(stmt).first()


def case_scope_check(db: Session, user: User, case: Case) -> bool:
    if user_has_permission(user, "case.read.assigned"):
        if get_active_assignment(db, case.id, user.id):
            return True
    if not case_product_module_allowed(user, case.product_module):
        return False
    if user_has_permission(user, "admin.override") or user_has_permission(user, "case.read.all"):
        return True
    if user_has_permission(user, "case.read.team"):
        if case.case_manager_user_id == user.id or case.region == user.region:
            return True
    if user_has_permission(user, "case.read.scoped"):
        return case_product_module_allowed(user, case.product_module)
    return False


def require_case_access(case_id_param: str = "case_id"):
    from app.api.deps import get_current_user

    def checker(
        case_id: int,
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> tuple[User, Case]:
        case = db.get(Case, case_id)
        if not case:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
        if not case_scope_check(db, user, case):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Case access denied")
        return user, case

    return checker
