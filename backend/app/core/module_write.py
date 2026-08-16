"""Enforce per-module view/write grants on mutating API operations."""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.module_access import is_view_only_user, module_bypass, user_has_feature
from app.core.modules import MODULE_BY_ID
from app.core.rbac_access import build_module_registry, user_can_write_module, user_module_enabled
from app.models.case import Case
from app.models.case_therapist_transition import (
    CaseTherapistTransition,
    CaseTherapistTransitionStatus,
)
from app.models.user import User
from app.services import therapist_transition_service

CLINICAL_PROGRAMME_IDS = frozenset({"homecare", "shadow_support"})

FEATURE_PRIMARY_MODULE: dict[str, str] = {
    "invoices": "billing",
    "dashboard": "billing",
}

ORG_TICKET_MODULE_IDS: tuple[str, ...] = ("billing", "hr_ops")


def _raise_read_only(detail: str = "View-only access — changes are not allowed") -> None:
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


def programme_module_ids_for_product(product_module: str, db: Session | None = None) -> list[str]:
    product = (product_module or "homecare").strip().lower()
    registry = build_module_registry(db)
    ids: list[str] = []
    for mid, mod in registry.items():
        if mid == product or product in mod.case_product_modules:
            ids.append(mid)
    if not ids and product:
        ids.append(product)
    return ids


def user_can_write_product_module(user: User, product_module: str, db: Session | None = None) -> bool:
    if module_bypass(user):
        return True
    if is_view_only_user(user):
        return False
    for mid in programme_module_ids_for_product(product_module, db):
        if user_module_enabled(user, mid) and user_can_write_module(user, mid):
            return True
    return False


def user_can_write_org_desk_tickets(user: User) -> bool:
    """Finance / HR desk queues — org modules, not clinical programme write."""
    if module_bypass(user):
        return True
    if is_view_only_user(user):
        return False
    if not user_has_feature(user, "tickets"):
        return False
    for mid in ORG_TICKET_MODULE_IDS:
        mod = MODULE_BY_ID.get(mid)
        if not mod or not any(f.id == "tickets" for f in mod.features):
            continue
        if user_module_enabled(user, mid) and user_can_write_module(user, mid):
            return True
    return False


def user_can_write_feature(
    user: User,
    feature_id: str,
    *,
    product_module: str | None = None,
    db: Session | None = None,
) -> bool:
    if module_bypass(user):
        return True
    if is_view_only_user(user):
        return False
    if not user_has_feature(user, feature_id, db):
        return False
    primary = FEATURE_PRIMARY_MODULE.get(feature_id)
    if primary:
        return user_module_enabled(user, primary) and user_can_write_module(user, primary)
    if feature_id == "tickets":
        if user_can_write_org_desk_tickets(user):
            return True
        if product_module:
            return user_can_write_product_module(user, product_module, db)
        for mid in user.module_assignments or []:
            if user_module_enabled(user, mid) and user_can_write_module(user, mid):
                return True
        return False
    if product_module:
        return user_can_write_product_module(user, product_module, db)
    for mid in user.module_assignments or []:
        if str(mid).strip().lower() == "billing":
            continue
        if user_module_enabled(user, mid) and user_can_write_module(user, mid):
            return True
    return False


def ensure_case_transition_allows_write(
    case: Case,
    db: Session,
    *,
    allow_during_transition: bool = False,
) -> None:
    if allow_during_transition:
        return
    therapist_transition_service.complete_due_transition_for_case(db, case.id)
    open_transition = db.scalars(
        select(CaseTherapistTransition.id)
        .where(
            CaseTherapistTransition.case_id == case.id,
            CaseTherapistTransition.status.in_(
                [
                    CaseTherapistTransitionStatus.SCHEDULED,
                    CaseTherapistTransitionStatus.ACTIVE,
                ]
            ),
        )
        .limit(1)
    ).first()
    if open_transition:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "This case is in a therapist transition. Other case changes are paused "
                "until the handover is completed or cancelled."
            ),
        )


def ensure_case_write_access(
    user: User,
    case: Case,
    db: Session | None = None,
    *,
    allow_during_transition: bool = False,
) -> None:
    if db is not None:
        ensure_case_transition_allows_write(
            case,
            db,
            allow_during_transition=allow_during_transition,
        )
    if module_bypass(user):
        return
    if is_view_only_user(user):
        _raise_read_only()
    if not user_can_write_product_module(user, case.product_module, db):
        product = case.product_module or "homecare"
        _raise_read_only(f"No edit access for the {product} programme module")


def ensure_product_module_write_access(
    user: User,
    product_module: str,
    db: Session | None = None,
) -> None:
    if module_bypass(user):
        return
    if is_view_only_user(user):
        _raise_read_only()
    if not user_can_write_product_module(user, product_module, db):
        _raise_read_only(f"No edit access for the {product_module} programme module")


def ensure_billing_write_access(user: User) -> None:
    if module_bypass(user):
        return
    if is_view_only_user(user):
        _raise_read_only()
    if not (user_module_enabled(user, "billing") and user_can_write_module(user, "billing")):
        _raise_read_only("No edit access for the billing module")


def ensure_feature_write_access(
    user: User,
    feature_id: str,
    *,
    product_module: str | None = None,
    db: Session | None = None,
) -> None:
    if not user_can_write_feature(user, feature_id, product_module=product_module, db=db):
        _raise_read_only(f"No edit access for feature: {feature_id}")


def _assigned_cm_on_caseload(user: User, case: Case) -> bool:
    from app.core.permissions import user_has_permission

    return bool(
        user_has_permission(user, "case.read.team")
        and case.case_manager_user_id == user.id
    )


def ensure_log_review_write_access(user: User, case: Case, db: Session | None = None) -> None:
    """Log approve/reject: assigned CM may act on their caseload without programme module write."""
    if module_bypass(user):
        return
    if is_view_only_user(user):
        _raise_read_only()
    if _assigned_cm_on_caseload(user, case):
        return
    ensure_case_write_access(user, case, db, allow_during_transition=True)
    ensure_feature_write_access(user, "session_logs", product_module=case.product_module, db=db)


def guard_clinical_case(
    user: User,
    case: Case,
    db: Session | None = None,
    *,
    feature: str | None = None,
) -> None:
    """Case programme write plus optional feature (reports, iep, session_logs, …)."""
    ensure_case_write_access(user, case, db)
    if feature:
        ensure_feature_write_access(user, feature, product_module=case.product_module, db=db)
