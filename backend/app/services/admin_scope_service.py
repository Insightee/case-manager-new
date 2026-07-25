from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.module_access import get_allowed_case_product_modules
from app.core.permissions import user_has_permission
from app.models.case import Case
from app.models.user import User


def team_case_access_clause(user: User):
    """Cases visible to case.read.team users — assigned caseload only."""
    return Case.case_manager_user_id == user.id


def team_case_in_scope(user: User, case: Case) -> bool:
    return case.case_manager_user_id == user.id


def case_row_scope_clause(user: User):
    """Return a Case filter for list/analytics queries, or None when unrestricted."""
    if user_has_permission(user, "admin.override") or user_has_permission(user, "case.read.all"):
        return None
    if user_has_permission(user, "case.read.team"):
        return team_case_access_clause(user)
    allowed = get_allowed_case_product_modules(user)
    if allowed is None:
        return None
    if not allowed:
        return Case.id < 0
    return Case.product_module.in_(allowed)


def apply_case_scope(stmt, user: User):
    """Apply product-module and team/region filters on queries that join Case."""
    if user_has_permission(user, "admin.override") or user_has_permission(user, "case.read.all"):
        return stmt

    if user_has_permission(user, "case.read.team"):
        return stmt.where(team_case_access_clause(user))

    allowed = get_allowed_case_product_modules(user)
    if allowed is None:
        pass
    elif not allowed:
        stmt = stmt.where(Case.id < 0)
    else:
        stmt = stmt.where(Case.product_module.in_(allowed))

    if user_has_permission(user, "case.read.scoped"):
        return stmt

    return stmt.where(Case.id < 0)


def scoped_case_ids_subquery(user: User):
    stmt = select(Case.id)
    return apply_case_scope(stmt, user)


def user_sees_global_cases(user: User) -> bool:
    return user_has_permission(user, "admin.override") or user_has_permission(
        user, "case.read.all"
    )
