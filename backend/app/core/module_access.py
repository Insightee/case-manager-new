"""Module and feature access for staff portals.

Per-user ``feature_overrides`` (admin UI) adjust the feature list returned to the client.
Server enforcement is primarily **module-level** via the RBAC catalog and ``require_module``;
overrides do not bypass permission checks on individual API routes unless a handler
calls an explicit feature guard.
"""
from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.modules import MODULE_BY_ID, MODULE_SCOPED_ROLES, ModuleFeature
from app.core.rbac_access import (
    build_module_registry,
    disabled_features_for_module,
    effective_features_for_user as rbac_effective_features,
    user_module_enabled,
)
from app.models.user import User


def _user_has_permission(user: User, permission: str) -> bool:
    from app.core.permissions import user_has_permission

    return user_has_permission(user, permission)


def module_bypass(user: User) -> bool:
    if "SUPER_ADMIN" in user.role_names:
        return True
    if _user_has_permission(user, "admin.override"):
        return True
    return False


def normalize_module_ids(module_ids: list[str] | None) -> list[str]:
    if not module_ids:
        return []
    seen: set[str] = set()
    out: list[str] = []
    for raw in module_ids:
        mid = raw.strip().lower()
        if not mid or mid in seen:
            continue
        seen.add(mid)
        out.append(mid)
    return out


def validate_module_assignments(
    role_names: list[str],
    module_assignments: list[str] | None,
    db: Session | None = None,
) -> list[str]:
    from app.core.rbac_access import validate_access_payload

    try:
        return validate_access_payload(role_names, module_assignments, db)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


def get_allowed_case_product_modules(user: User, db: Session | None = None) -> set[str] | None:
    """None = all case product modules; empty set = no case-scoped data."""
    if module_bypass(user):
        return None
    registry = build_module_registry(db)
    assigned = normalize_module_ids(user.module_assignments)
    if not assigned:
        return set()
    allowed: set[str] = set()
    for mid in assigned:
        if not user_module_enabled(user, mid):
            continue
        mod = registry.get(mid)
        if mod:
            allowed.update(mod.case_product_modules)
        elif mid not in MODULE_BY_ID:
            allowed.add(mid)
    return allowed


def case_product_module_allowed(user: User, product_module: str, db: Session | None = None) -> bool:
    allowed = get_allowed_case_product_modules(user, db)
    if allowed is None:
        return True
    if not allowed:
        return False
    return product_module in allowed


def _feature_granted_by_role(user: User, feature: ModuleFeature) -> bool:
    if not feature.permissions:
        return True
    return any(_user_has_permission(user, p) for p in feature.permissions)


def get_user_features(user: User, db: Session | None = None) -> list[str]:
    return rbac_effective_features(user, db)


def user_has_feature(user: User, feature_id: str, db: Session | None = None) -> bool:
    feats = get_user_features(user, db)
    if "*" in feats:
        return True
    return feature_id in feats


def is_view_only_user(user: User) -> bool:
    """True when the user is restricted to read-only portal access."""
    if module_bypass(user):
        return False
    if getattr(user, "is_view_only", False):
        return True
    from app.core.permissions import user_has_permission

    return user_has_permission(user, "admin.view_only")


def require_feature(feature_id: str):
    def checker(user: User) -> User:
        if not user_has_feature(user, feature_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Module access required for feature: {feature_id}",
            )
        return user

    return checker


def modules_for_api(user: User, db: Session | None = None) -> list[dict]:
    from app.core.modules import PRODUCT_MODULES
    from app.core.rbac_access import user_module_grant

    if module_bypass(user):
        return [
            {
                "id": m.id,
                "label": m.label,
                "description": m.description,
                "case_product_modules": list(m.case_product_modules),
                "features": [f.id for f in m.features],
            }
            for m in PRODUCT_MODULES
        ]
    registry = build_module_registry(db)
    assigned = normalize_module_ids(user.module_assignments)
    out = []
    for mid in assigned:
        if not user_module_enabled(user, mid):
            continue
        m = registry.get(mid)
        if not m:
            continue
        grant = user_module_grant(user, mid) or {}
        disabled = disabled_features_for_module(user, mid)
        out.append(
            {
                "id": m.id,
                "label": m.label,
                "description": m.description,
                "case_product_modules": list(m.case_product_modules),
                "access": grant.get("access", "write"),
                "features": [
                    f.id
                    for f in m.features
                    if f.id not in disabled and _feature_granted_by_role(user, f)
                ],
            }
        )
    return out
