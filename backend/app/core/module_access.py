from __future__ import annotations

from fastapi import HTTPException, status

from app.core.modules import MODULE_BY_ID, MODULE_SCOPED_ROLES, PRODUCT_MODULES, ModuleFeature
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


def validate_module_assignments(role_names: list[str], module_assignments: list[str] | None) -> list[str]:
    normalized = normalize_module_ids(module_assignments)
    unknown = [m for m in normalized if m not in MODULE_BY_ID]
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown modules: {', '.join(unknown)}",
        )
    roles = {r.upper() for r in role_names}
    if "SUPER_ADMIN" in roles:
        return normalized
    if roles.intersection(MODULE_SCOPED_ROLES) and not normalized:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one product module is required for this role.",
        )
    return normalized


def get_allowed_case_product_modules(user: User) -> set[str] | None:
    """None = all case product modules; empty set = no case-scoped data."""
    if module_bypass(user):
        return None
    assigned = normalize_module_ids(user.module_assignments)
    if not assigned:
        return set()
    allowed: set[str] = set()
    for mid in assigned:
        mod = MODULE_BY_ID.get(mid)
        if mod:
            allowed.update(mod.case_product_modules)
    return allowed


def case_product_module_allowed(user: User, product_module: str) -> bool:
    allowed = get_allowed_case_product_modules(user)
    if allowed is None:
        return True
    if not allowed:
        return False
    return product_module in allowed


def _feature_granted_by_role(user: User, feature: ModuleFeature) -> bool:
    if not feature.permissions:
        return True
    return any(_user_has_permission(user, p) for p in feature.permissions)


def get_user_features(user: User) -> list[str]:
    if module_bypass(user):
        return ["*"]
    assigned = normalize_module_ids(user.module_assignments)
    features: set[str] = set()
    for mid in assigned:
        mod = MODULE_BY_ID.get(mid)
        if not mod:
            continue
        for feat in mod.features:
            if _feature_granted_by_role(user, feat):
                features.add(feat.id)
    return sorted(features)


def user_has_feature(user: User, feature_id: str) -> bool:
    feats = get_user_features(user)
    if "*" in feats:
        return True
    return feature_id in feats


def require_feature(feature_id: str):
    def checker(user: User) -> User:
        if not user_has_feature(user, feature_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Module access required for feature: {feature_id}",
            )
        return user

    return checker


def modules_for_api(user: User) -> list[dict]:
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
    assigned = normalize_module_ids(user.module_assignments)
    out = []
    for mid in assigned:
        m = MODULE_BY_ID.get(mid)
        if m:
            out.append(
                {
                    "id": m.id,
                    "label": m.label,
                    "description": m.description,
                    "case_product_modules": list(m.case_product_modules),
                    "features": [f.id for f in m.features if _feature_granted_by_role(user, f)],
                }
            )
    return out
