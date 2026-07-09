from __future__ import annotations

from datetime import date
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.module_access import case_product_module_allowed, get_allowed_case_product_modules
from app.core.pagination import normalize_pagination, paginate_query, paginated_response
from app.core.permissions import case_scope_check, user_has_permission
from app.core.billing_validation import case_billing_dict
from app.services.address_service import case_service_address_read
from app.models.assignment import CaseAssignment, CaseAssignmentStatus
from app.models.case import Case, CaseStatus
from app.models.user import User
from app.services.admin_scope_service import team_case_access_clause
from app.services.case_portal_visibility import portal_visible_case_status_filter


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
            .where(portal_visible_case_status_filter(Case.status))
            .distinct()
        )
    elif user_has_permission(user, "admin.override") or user_has_permission(user, "case.read.all"):
        stmt = _apply_module_filter(stmt, user)
    elif user_has_permission(user, "case.read.team"):
        stmt = stmt.where(team_case_access_clause(user))
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
            .where(portal_visible_case_status_filter(Case.status))
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
            .where(portal_visible_case_status_filter(Case.status))
            .distinct()
        )

    rows, total = paginate_query(db, stmt, page=page, page_size=page_size)
    # Post-filter for edge roles that need case_scope_check (school coordinator)
    if not assigned_only and user_has_permission(user, "case.read.scoped") and not user_has_permission(
        user, "case.read.all"
    ):
        rows = [c for c in rows if case_scope_check(db, user, c)]
        total = len(rows)

    items = [case_to_read(c, db) for c in rows]
    return paginated_response(items, total, page, page_size)


def get_case(db: Session, case_id: int) -> Case | None:
    return db.scalars(select(Case).where(Case.id == case_id).options(selectinload(Case.child))).first()


def case_child_display_name(case: Case | None) -> str | None:
    if not case:
        return None
    return case.child.full_name if case.child else None


def case_manager_contact(db: Session, case: Case) -> tuple[Optional[str], Optional[str]]:
    if not case.case_manager_user_id:
        return None, None
    cm = db.get(User, case.case_manager_user_id)
    if not cm:
        return None, None
    return cm.full_name, cm.email


def _child_age_label(dob: date | None) -> str | None:
    if not dob:
        return None
    today = date.today()
    years = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
    return f"{years} years old"


def _parent_names_for_child(db: Session, child_id: int) -> str | None:
    from app.models.parent import ParentGuardian, parent_child_link

    rows = db.execute(
        select(User.full_name)
        .select_from(parent_child_link)
        .join(ParentGuardian, parent_child_link.c.parent_guardian_id == ParentGuardian.id)
        .join(User, ParentGuardian.user_id == User.id)
        .where(parent_child_link.c.child_id == child_id)
    ).all()
    names = [n for (n,) in rows if n]
    return " and ".join(names) if names else None


def _primary_therapist_name(db: Session, case_id: int) -> str | None:
    row = db.scalar(
        select(User.full_name)
        .select_from(CaseAssignment)
        .join(User, CaseAssignment.therapist_user_id == User.id)
        .where(
            CaseAssignment.case_id == case_id,
            CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
        )
        .order_by(CaseAssignment.start_date.desc())
        .limit(1)
    )
    return row


def case_to_read(case: Case, db: Session | None = None) -> dict:
    service_addr = case_service_address_read(case)
    cm_name, cm_email = (None, None)
    child_dob = case.child.date_of_birth if case.child else None
    parent_name = None
    therapist_name = None
    if db is not None:
        cm_name, cm_email = case_manager_contact(db, case)
        if case.child_id:
            parent_name = _parent_names_for_child(db, case.child_id)
        therapist_name = _primary_therapist_name(db, case.id)
    return {
        "id": case.id,
        "case_code": case.case_code,
        "external_case_ref": case.external_case_ref,
        "child_id": case.child_id,
        "child_name": case.child.full_name if case.child else None,
        "service_type": case.service_type,
        "product_module": case.product_module,
        "status": case.status,
        "status_effective_date": case.status_effective_date,
        "status_reason": case.status_reason,
        "status_changed_by_user_id": case.status_changed_by_user_id,
        "case_manager_user_id": case.case_manager_user_id,
        "case_manager_name": cm_name,
        "case_manager_email": cm_email,
        "notes": case.notes,
        "region": case.region,
        "operational_stage": case.operational_stage,
        "created_at": case.created_at,
        "billing_updated_at": case.billing_updated_at,
        "service_address": service_addr,
        "maps_url": service_addr.maps_url if service_addr else None,
        "service_location_type": case.service_location_type,
        "billing_address_same_as_service": case.billing_address_same_as_service,
        "billing_address_line1": case.billing_address_line1,
        "billing_address_line2": case.billing_address_line2,
        "billing_address_city": case.billing_address_city,
        "billing_address_state": case.billing_address_state,
        "billing_address_pincode": case.billing_address_pincode,
        "billing_address_landmark": case.billing_address_landmark,
        "child_date_of_birth": child_dob,
        "child_age_label": _child_age_label(child_dob),
        "parent_name": parent_name,
        "therapist_name": therapist_name,
        **case_billing_dict(case),
    }
