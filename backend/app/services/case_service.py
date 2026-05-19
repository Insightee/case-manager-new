from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.module_access import case_product_module_allowed
from app.core.permissions import case_scope_check, user_has_permission
from app.core.billing_validation import case_billing_dict
from app.services.address_service import case_service_address_read
from app.models.case import Case
from app.models.child import Child
from app.models.user import User


def list_cases_for_user(db: Session, user: User, assigned_only: bool = False) -> list[Case]:
    stmt = select(Case).options(selectinload(Case.child)).order_by(Case.case_code)
    cases = list(db.scalars(stmt).all())
    if user_has_permission(user, "case.read.all") and not assigned_only:
        return [c for c in cases if case_product_module_allowed(user, c.product_module)]
    if assigned_only or user_has_permission(user, "case.read.assigned"):
        from app.models.assignment import CaseAssignment, CaseAssignmentStatus

        assigned_ids = db.scalars(
            select(CaseAssignment.case_id).where(
                CaseAssignment.therapist_user_id == user.id,
                CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
            )
        ).all()
        return [c for c in cases if c.id in assigned_ids]
    return [c for c in cases if case_scope_check(db, user, c)]


def get_case(db: Session, case_id: int) -> Case | None:
    return db.scalars(select(Case).where(Case.id == case_id).options(selectinload(Case.child))).first()


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
