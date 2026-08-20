from __future__ import annotations

from typing import Optional

from sqlalchemy import exists, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.module_access import get_allowed_case_product_modules
from app.core.pagination import normalize_pagination, paginate_query, paginated_response
from app.core.permissions import case_scope_check, user_has_permission
from app.core.billing_validation import case_billing_dict
from app.services.address_service import case_service_address_read
from app.models.assignment import CaseAssignment, CaseAssignmentStatus
from app.models.case import Case, CaseStatus
from app.models.case_therapist_transition import (
    CaseTherapistTransition,
    CaseTherapistTransitionStatus,
)
from app.models.child import Child
from app.models.user import User
from app.services.admin_scope_service import team_case_access_clause
from app.services.case_portal_visibility import portal_visible_case_status_filter

_EMPTY_ZOHO_MARKERS = frozenset({"", "-", "—", "–", "n/a", "na", "none", "null"})


def normalize_zoho_id(value: str | None) -> str | None:
    text = (value or "").strip()
    if not text or text.lower() in _EMPTY_ZOHO_MARKERS:
        return None
    return text[:64]


def normalize_case_code(value: str | None) -> str | None:
    text = (value or "").strip().upper()
    if not text or text.lower() in _EMPTY_ZOHO_MARKERS:
        return None
    return text


def _apply_module_filter(stmt, user: User):
    allowed = get_allowed_case_product_modules(user)
    if allowed is not None:
        if not allowed:
            return stmt.where(Case.id < 0)  # empty
        stmt = stmt.where(Case.product_module.in_(allowed))
    return stmt


def _apply_case_search(stmt, search: str | None):
    """Filter by case code, child name, or active therapist name."""
    q = (search or "").strip()
    if not q:
        return stmt
    pattern = f"%{q}%"
    child_full = func.trim(Child.first_name + " " + Child.last_name)
    therapist_match = exists(
        select(CaseAssignment.id)
        .join(User, User.id == CaseAssignment.therapist_user_id)
        .where(
            CaseAssignment.case_id == Case.id,
            CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
            User.full_name.ilike(pattern),
        )
    )
    transition_match = False
    if q.lower() in {"transition", "in transition", "handover"}:
        transition_match = exists(
            select(CaseTherapistTransition.id).where(
                CaseTherapistTransition.case_id == Case.id,
                CaseTherapistTransition.status.in_(
                    [
                        CaseTherapistTransitionStatus.SCHEDULED,
                        CaseTherapistTransitionStatus.ACTIVE,
                    ]
                ),
            )
        )
    return (
        stmt.outerjoin(Child, Child.id == Case.child_id)
        .where(
            or_(
                Case.case_code.ilike(pattern),
                Case.product_module.ilike(pattern),
                Case.service_type.ilike(pattern),
                Child.first_name.ilike(pattern),
                Child.last_name.ilike(pattern),
                child_full.ilike(pattern),
                therapist_match,
                transition_match,
            )
        )
        .distinct()
    )


def _active_therapist_names(db: Session, case_ids: list[int]) -> dict[int, str]:
    if not case_ids:
        return {}
    rows = db.execute(
        select(CaseAssignment.case_id, User.full_name)
        .join(User, User.id == CaseAssignment.therapist_user_id)
        .where(
            CaseAssignment.case_id.in_(case_ids),
            CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
        )
        .order_by(CaseAssignment.id.desc())
    ).all()
    out: dict[int, str] = {}
    for case_id, name in rows:
        if case_id not in out and name:
            out[int(case_id)] = name
    return out


def _cases_in_transition(db: Session, case_ids: list[int]) -> set[int]:
    if not case_ids:
        return set()
    return {
        int(case_id)
        for case_id in db.scalars(
            select(CaseTherapistTransition.case_id)
            .where(
                CaseTherapistTransition.case_id.in_(case_ids),
                CaseTherapistTransition.status.in_(
                    [
                        CaseTherapistTransitionStatus.SCHEDULED,
                        CaseTherapistTransitionStatus.ACTIVE,
                    ]
                ),
            )
            .distinct()
        ).all()
    }


def list_cases_for_user(
    db: Session,
    user: User,
    *,
    assigned_only: bool = False,
    status: Optional[CaseStatus] = None,
    product_module: Optional[str] = None,
    search: Optional[str] = None,
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

    stmt = _apply_case_search(stmt, search)

    rows, total = paginate_query(db, stmt, page=page, page_size=page_size)
    # Post-filter for edge roles that need case_scope_check (school coordinator)
    if not assigned_only and user_has_permission(user, "case.read.scoped") and not user_has_permission(
        user, "case.read.all"
    ):
        rows = [c for c in rows if case_scope_check(db, user, c)]
        total = len(rows)

    therapist_by_case = _active_therapist_names(db, [c.id for c in rows])
    transition_case_ids = _cases_in_transition(db, [c.id for c in rows])
    items = []
    for c in rows:
        item = case_to_read(c, db, resolve_therapist=False, viewer=user)
        item["therapist_name"] = therapist_by_case.get(c.id)
        item["in_transition"] = c.id in transition_case_ids
        items.append(item)
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


def case_to_read(
    case: Case,
    db: Session | None = None,
    *,
    resolve_therapist: bool = True,
    viewer: User | None = None,
) -> dict:
    service_addr = case_service_address_read(case)
    cm_name, cm_email = (None, None)
    therapist_name = None
    access_as_mentor = False
    if db is not None:
        cm_name, cm_email = case_manager_contact(db, case)
        if resolve_therapist:
            therapist_name = _active_therapist_names(db, [case.id]).get(case.id)
        if viewer is not None:
            from app.services.mentor_scope_service import is_mentor_only_on_case

            access_as_mentor = is_mentor_only_on_case(db, viewer, case)
    in_transition = bool(db and case.id in _cases_in_transition(db, [case.id]))
    return {
        "id": case.id,
        "case_code": case.case_code,
        "external_case_ref": case.external_case_ref,
        "zoho_id": case.zoho_id,
        "child_id": case.child_id,
        "child_name": case.child.full_name if case.child else None,
        "therapist_name": therapist_name,
        "in_transition": in_transition,
        "service_type": case.service_type,
        "product_module": case.product_module,
        "day_type": case.day_type.value if case.day_type else None,
        "status": case.status,
        "status_effective_date": case.status_effective_date,
        "status_reason": case.status_reason,
        "status_changed_by_user_id": case.status_changed_by_user_id,
        "case_manager_user_id": case.case_manager_user_id,
        "case_manager_name": cm_name,
        "case_manager_email": cm_email,
        "access_as_mentor": access_as_mentor,
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
        **case_billing_dict(case),
    }
