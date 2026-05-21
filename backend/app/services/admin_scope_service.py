from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.module_access import get_allowed_case_product_modules
from app.core.permissions import user_has_permission
from app.models.case import Case
from app.models.user import User


def apply_case_scope(stmt, user: User):
    """Apply product-module and team/region filters on queries that join Case."""
    allowed = get_allowed_case_product_modules(user)
    if allowed is None:
        pass
    elif not allowed:
        stmt = stmt.where(Case.id < 0)
    else:
        stmt = stmt.where(Case.product_module.in_(allowed))

    if user_has_permission(user, "admin.override") or user_has_permission(user, "case.read.all"):
        return stmt

    if user_has_permission(user, "case.read.team"):
        stmt = stmt.where(
            or_(Case.case_manager_user_id == user.id, Case.region == user.region)
        )
    elif not user_has_permission(user, "case.read.scoped"):
        stmt = stmt.where(Case.id < 0)

    return stmt


def scoped_case_ids_subquery(user: User):
    stmt = select(Case.id)
    return apply_case_scope(stmt, user)


def user_sees_global_cases(user: User) -> bool:
    return user_has_permission(user, "admin.override") or user_has_permission(
        user, "case.read.all"
    )
