from __future__ import annotations

from typing import Optional

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.module_access import case_product_module_allowed, get_allowed_case_product_modules
from app.core.pagination import normalize_pagination, paginate_query, paginated_response
from app.core.permissions import case_scope_check, user_has_permission
from app.core.billing_validation import case_billing_dict
from app.services.address_service import case_service_address_read
from app.models.assignment import CaseAssignment, CaseAssignmentStatus
from app.models.case import Case, CaseStatus
from app.models.user import User


def _apply_module_filter(stmt, user: User):
    allowed = get_allowed_case_product_modules(user)
    if allowed is not None:
        if not allowed:
            return stmt.where(Case.id < 0)  # empty
        stmt = stmt.where(Case.product_module.in_(allowed))
    return stmt


def list_cases_for_user(
    db: Session,
    user: User,
    *,
    assigned_only: bool = False,
    status: Optional[CaseStatus] = None,
    product_module: Optional[str] = None,
    page: int = 1,
    page_size: int = 25,
) -> dict:
    page, page_size = normalize_pagination(page, page_size)
    stmt = select(Case).options(selectinload(Case.child)).order_by(Case.case_code)

    if status is not None:
        stmt = stmt.where(Case.status == status)
    if product_module is not None:
        stmt = stmt.where(Case.product_module == product_module)

    if assigned_only or (
        user_has_permission(user, "case.read.assigned")
        and not user_has_permission(user, "case.read.all")
        and not user_has_permission(user, "case.read.team")
    ):
        stmt = (
            stmt.join(
                CaseAssignment,
                (CaseAssignment.case_id == Case.id)
                & (CaseAssignment.therapist_user_id == user.id)
                & (CaseAssignment.status == CaseAssignmentStatus.ACTIVE),
            )
            .distinct()
        )
    elif user_has_permission(user, "admin.override") or user_has_permission(user, "case.read.all"):
        stmt = _apply_module_filter(stmt, user)
    elif user_has_permission(user, "case.read.team"):
        stmt = stmt.where(
            or_(Case.case_manager_user_id == user.id, Case.region == user.region)
        )
        stmt = _apply_module_filter(stmt, user)
    elif user_has_permission(user, "case.read.scoped"):
        stmt = _apply_module_filter(stmt, user)
    elif user_has_permission(user, "case.read.assigned"):
        stmt = (
            stmt.join(
                CaseAssignment,
                (CaseAssignment.case_id == Case.id)
                & (CaseAssignment.therapist_user_id == user.id)
                & (CaseAssignment.status == CaseAssignmentStatus.ACTIVE),
            )
            .distinct()
        )
    else:
        # Fallback: only cases user can scope-check (rare); load assigned set in SQL
        stmt = (
            stmt.join(
                CaseAssignment,
                (CaseAssignment.case_id == Case.id)
                & (CaseAssignment.therapist_user_id == user.id)
                & (CaseAssignment.status == CaseAssignmentStatus.ACTIVE),
            )
            .distinct()
        )

    rows, total = paginate_query(db, stmt, page=page, page_size=page_size)
    # Post-filter for edge roles that need case_scope_check (school coordinator)
    if not assigned_only and user_has_permission(user, "case.read.scoped") and not user_has_permission(
        user, "case.read.all"
    ):
        rows = [c for c in rows if case_scope_check(db, user, c)]
        total = len(rows)

    items = [case_to_read(c) for c in rows]
    return paginated_response(items, total, page, page_size)


def get_case(db: Session, case_id: int) -> Case | None:
    return db.scalars(select(Case).where(Case.id == case_id).options(selectinload(Case.child))).first()


def case_child_display_name(case: Case | None) -> str | None:
    if not case:
        return None
    return case.child.full_name if case.child else None


def case_to_read(case: Case) -> dict:
    service_addr = case_service_address_read(case)
    return {
        "id": case.id,
        "case_code": case.case_code,
        "child_id": case.child_id,
        "child_name": case.child.full_name if case.child else None,
        "service_type": case.service_type,
        "product_module": case.product_module,
        "status": case.status,
        "case_manager_user_id": case.case_manager_user_id,
        "region": case.region,
        "operational_stage": case.operational_stage,
        "created_at": case.created_at,
        "billing_updated_at": case.billing_updated_at,
        "service_address": service_addr,
        "maps_url": service_addr.maps_url if service_addr else None,
        **case_billing_dict(case),
    }
