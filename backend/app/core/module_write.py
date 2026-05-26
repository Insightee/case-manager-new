"""Enforce per-module view/write grants on mutating API operations."""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.module_access import is_view_only_user, module_bypass, user_has_feature
from app.core.rbac_access import build_module_registry, user_can_write_module, user_module_enabled
from app.models.case import Case
from app.models.user import User

CLINICAL_PROGRAMME_IDS = frozenset({"homecare", "shadow_support"})

FEATURE_PRIMARY_MODULE: dict[str, str] = {
    "invoices": "billing",
    "dashboard": "billing",
}


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
    if not user_has_feature(user, feature_id):
        return False
    primary = FEATURE_PRIMARY_MODULE.get(feature_id)
    if primary:
        return user_module_enabled(user, primary) and user_can_write_module(user, primary)
    if product_module:
        return user_can_write_product_module(user, product_module, db)
    for mid in user.module_assignments or []:
        if str(mid).strip().lower() == "billing":
            continue
        if user_module_enabled(user, mid) and user_can_write_module(user, mid):
            return True
    return False


def ensure_case_write_access(user: User, case: Case, db: Session | None = None) -> None:
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
