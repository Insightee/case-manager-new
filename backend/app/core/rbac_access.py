"""RBAC: module grants, feature overrides, and effective access resolution."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.core.modules import MODULE_BY_ID, MODULE_SCOPED_ROLES, PRODUCT_MODULES, ROLE_DEFAULT_MODULES, ModuleFeature, ProductModule

# Staff roles configurable in the access editor (not therapist/parent/school).
ASSIGNABLE_STAFF_ROLES: tuple[dict[str, str], ...] = (
    {"id": "MODULE_ADMIN", "label": "Module Admin", "description": "People, modules, cases, documents, approvals."},
    {"id": "CASE_MANAGER", "label": "Case Manager", "description": "Clinical caseload, reports, IEP, incidents on assigned cases."},
    {"id": "FINANCE", "label": "Finance", "description": "Invoices, payouts, client payment claims."},
    {"id": "HR", "label": "HR", "description": "People, leave, therapist HR operations."},
    {"id": "SUPER_ADMIN", "label": "Super Admin", "description": "Full access; use sparingly."},
)

DEPRECATED_STAFF_ROLES: frozenset[str] = frozenset({"SUPERVISOR", "VIEWER"})
LEGACY_ADMIN_ROLE = "ADMIN"


def validate_assignable_staff_roles(role_names: list[str]) -> None:
    """Reject retired roles and legacy ADMIN for new assignments."""
    upper = {str(r).strip().upper() for r in role_names if r}
    if not upper:
        raise ValueError("At least one role is required")
    retired = upper & DEPRECATED_STAFF_ROLES
    if retired:
        raise ValueError(
            f"Role(s) {', '.join(sorted(retired))} are retired. "
            "Use Case Manager with per-module view access for read-only staff."
        )
    if LEGACY_ADMIN_ROLE in upper:
        raise ValueError(
            "Legacy ADMIN is not assignable. Use MODULE_ADMIN for operations administrators."
        )

NAV_BY_FEATURE: dict[str, str] = {
    "cases": "Cases & case pipeline",
    "session_logs": "Workbench & session logs",
    "reports": "Reports & observation checklists",
    "iep": "IEP builder & attachments",
    "cm_meetings": "CM meetings hub",
    "invoices": "Invoices & client payment claims",
    "tickets": "Support tickets",
    "incidents": "Incidents",
    "dashboard": "Finance dashboard",
}


def build_module_registry(db: Session | None = None) -> dict[str, ProductModule]:
    """Fixed modules plus active service categories."""
    registry: dict[str, ProductModule] = dict(MODULE_BY_ID)
    if db is None:
        return registry
    try:
        from sqlalchemy import inspect as sa_inspect
        from sqlalchemy import select

        from app.core.database import engine
        from app.core.modules import _CLINICAL_FEATURES
        from app.models.service_category import ServiceCategory

        insp = sa_inspect(engine)
        if not insp.has_table("service_categories"):
            return registry
        rows = db.scalars(
            select(ServiceCategory)
            .where(ServiceCategory.is_active.is_(True))
            .order_by(ServiceCategory.sort_order, ServiceCategory.label)
        ).all()
        for cat in rows:
            if cat.id in registry:
                continue
            registry[cat.id] = ProductModule(
                id=cat.id,
                label=cat.label,
                description=cat.description or f"{cat.label} service programme.",
                case_product_modules=(cat.id,),
                features=_CLINICAL_FEATURES,
            )
    except Exception:
        pass
    return registry


def module_catalog_entries(db: Session | None = None) -> list[dict]:
    registry = build_module_registry(db)
    return [
        {
            "id": m.id,
            "label": m.label,
            "description": m.description,
            "case_product_modules": list(m.case_product_modules),
            "module_type": "service" if m.id not in MODULE_BY_ID else "programme",
            "features": [
                {"id": f.id, "label": f.label, "permissions": list(f.permissions)}
                for f in m.features
            ],
        }
        for m in registry.values()
    ]


def _normalize_grant_entry(raw: Any) -> dict:
    if not isinstance(raw, dict):
        return {"enabled": False, "access": "view"}
    access = str(raw.get("access", "write")).lower()
    if access not in ("view", "write"):
        access = "write"
    return {
        "enabled": bool(raw.get("enabled", True)),
        "access": access,
    }


def normalize_module_access_grants(
    grants: dict[str, Any] | None,
    *,
    module_ids: list[str] | None = None,
    view_only: bool = False,
) -> dict[str, dict]:
    """Build grants dict; fill from module_ids if grants empty."""
    out: dict[str, dict] = {}
    if grants:
        for mid, entry in grants.items():
            slug = str(mid).strip().lower()
            if slug:
                out[slug] = _normalize_grant_entry(entry)
    if not out and module_ids:
        access = "view" if view_only else "write"
        for mid in module_ids:
            slug = str(mid).strip().lower()
            if slug:
                out[slug] = {"enabled": True, "access": access}
    return out


def grants_to_module_assignments(grants: dict[str, dict] | None) -> list[str]:
    if not grants:
        return []
    return [mid for mid, g in grants.items() if g.get("enabled")]


def normalize_feature_overrides(raw: dict[str, Any] | None) -> dict[str, list[str]]:
    if not raw:
        return {}
    out: dict[str, list[str]] = {}
    for mid, val in raw.items():
        slug = str(mid).strip().lower()
        if not slug:
            continue
        if isinstance(val, dict):
            disabled = val.get("disabled") or val.get("disabled_features") or []
        elif isinstance(val, list):
            disabled = val
        else:
            disabled = []
        out[slug] = list(dict.fromkeys(str(f).strip() for f in disabled if f))
    return out


def sync_user_access_fields(
    user,
    *,
    role_names: list[str],
    module_assignments: list[str] | None = None,
    module_access_grants: dict | None = None,
    feature_overrides: dict | None = None,
    view_only: bool | None = None,
) -> None:
    """Persist grants/overrides and keep module_assignments in sync."""
    roles = {r.upper() for r in role_names}
    if "SUPER_ADMIN" in roles:
        user.module_assignments = []
        user.module_access_grants = {}
        user.feature_overrides = {}
        if view_only is not None:
            user.is_view_only = view_only
        return

    grants = normalize_module_access_grants(
        module_access_grants,
        module_ids=module_assignments,
        view_only=bool(view_only) if view_only is not None else getattr(user, "is_view_only", False),
    )
    user.module_access_grants = grants
    user.feature_overrides = normalize_feature_overrides(feature_overrides)
    user.module_assignments = grants_to_module_assignments(grants)
    if view_only is not None:
        user.is_view_only = view_only
        if view_only:
            for mid in list(user.module_access_grants.keys()):
                user.module_access_grants[mid] = {
                    **user.module_access_grants[mid],
                    "access": "view",
                }


def user_module_grant(user, module_id: str) -> dict | None:
    grants = getattr(user, "module_access_grants", None) or {}
    mid = module_id.strip().lower()
    if mid in grants:
        return _normalize_grant_entry(grants[mid])
    # Legacy: enabled if in module_assignments
    assigned = [str(m).strip().lower() for m in (user.module_assignments or [])]
    if mid in assigned:
        access = "view" if getattr(user, "is_view_only", False) else "write"
        return {"enabled": True, "access": access}
    return None


def user_module_enabled(user, module_id: str) -> bool:
    from app.core.module_access import module_bypass

    if module_bypass(user):
        return True
    grant = user_module_grant(user, module_id)
    return bool(grant and grant.get("enabled"))


def user_can_write_module(user, module_id: str) -> bool:
    from app.core.module_access import module_bypass

    if module_bypass(user):
        return True
    if getattr(user, "is_view_only", False):
        return False
    grant = user_module_grant(user, module_id)
    return bool(grant and grant.get("enabled") and grant.get("access") == "write")


def disabled_features_for_module(user, module_id: str) -> set[str]:
    overrides = getattr(user, "feature_overrides", None) or {}
    mid = module_id.strip().lower()
    raw = overrides.get(mid, [])
    if isinstance(raw, dict):
        raw = raw.get("disabled") or raw.get("disabled_features") or []
    return set(str(f) for f in raw)


def _feature_granted_by_role(user, feature: ModuleFeature) -> bool:
    from app.core.permissions import user_has_permission

    if not feature.permissions:
        return True
    return any(user_has_permission(user, p) for p in feature.permissions)


def effective_features_for_user(user, db: Session | None = None) -> list[str]:
    from app.core.module_access import module_bypass

    if module_bypass(user):
        return ["*"]
    registry = build_module_registry(db)
    feats: set[str] = set()
    for mid in user.module_assignments or []:
        mod = registry.get(str(mid).strip().lower())
        if not mod:
            continue
        if not user_module_enabled(user, mod.id):
            continue
        disabled = disabled_features_for_module(user, mod.id)
        for feat in mod.features:
            if feat.id in disabled:
                continue
            if _feature_granted_by_role(user, feat):
                feats.add(feat.id)
    if getattr(user, "is_view_only", False):
        feats.add("view_only")
    return sorted(feats)


def preview_access(
    *,
    role_names: list[str],
    module_access_grants: dict | None,
    feature_overrides: dict | None,
    view_only: bool = False,
    db: Session | None = None,
) -> dict:
    """Dry-run effective access for the access editor preview panel."""
    from types import SimpleNamespace

    from app.core.permissions import ROLE_PERMISSIONS

    roles = [r.upper() for r in role_names if r]
    perms: set[str] = set()
    for r in roles:
        perms.update(ROLE_PERMISSIONS.get(r, []))

    pu = SimpleNamespace(
        role_names=roles,
        module_assignments=grants_to_module_assignments(
            normalize_module_access_grants(module_access_grants, view_only=view_only)
        ),
        module_access_grants=normalize_module_access_grants(module_access_grants, view_only=view_only),
        feature_overrides=normalize_feature_overrides(feature_overrides),
        is_view_only=view_only,
        permission_names=perms,
    )

    registry = build_module_registry(db)
    portal_areas: list[str] = []
    warnings: list[str] = []
    enabled_modules = []

    for mid in pu.module_assignments:
        mod = registry.get(mid)
        if not mod:
            warnings.append(f"Unknown module: {mid}")
            continue
        grant = pu.module_access_grants.get(mid, {})
        enabled_modules.append(
            {
                "id": mod.id,
                "label": mod.label,
                "access": grant.get("access", "write"),
            }
        )
        disabled = disabled_features_for_module(pu, mod.id)
        for feat in mod.features:
            if feat.id in disabled:
                continue
            if not feat.permissions or any(p in perms for p in feat.permissions):
                label = NAV_BY_FEATURE.get(feat.id)
                if label:
                    portal_areas.append(label)
            elif feat.permissions:
                warnings.append(
                    f"{mod.label}: feature “{feat.label}” needs permissions your role does not include."
                )

    if view_only:
        portal_areas.append("Read-only mode (no create/update)")

    return {
        "roles": roles,
        "permissions": sorted(perms),
        "module_assignments": pu.module_assignments,
        "modules": enabled_modules,
        "features": effective_features_for_user_preview(pu, db),
        "portal_areas": sorted(set(portal_areas)),
        "warnings": warnings,
    }


def effective_features_for_user_preview(pu, db: Session | None) -> list[str]:
    registry = build_module_registry(db)
    feats: set[str] = set()
    for mid in pu.module_assignments or []:
        mod = registry.get(str(mid).strip().lower())
        if not mod:
            continue
        disabled = disabled_features_for_module(pu, mod.id)
        for feat in mod.features:
            if feat.id in disabled:
                continue
            if not feat.permissions or any(p in pu.permission_names for p in feat.permissions):
                feats.add(feat.id)
    if pu.is_view_only:
        feats.add("view_only")
    return sorted(feats)


def validate_access_payload(
    role_names: list[str],
    module_assignments: list[str] | None,
    db: Session | None = None,
) -> list[str]:
    """Return normalized module IDs; raises ValueError on unknown modules."""
    registry = build_module_registry(db)
    roles = {r.upper() for r in role_names}
    if "SUPER_ADMIN" in roles:
        return []
    normalized = []
    seen: set[str] = set()
    for raw in module_assignments or []:
        mid = raw.strip().lower()
        if not mid or mid in seen:
            continue
        if mid not in registry:
            raise ValueError(f"Unknown modules: {mid}")
        seen.add(mid)
        normalized.append(mid)
    if roles.intersection(MODULE_SCOPED_ROLES) and not normalized:
        raise ValueError("At least one product module is required for this role.")
    return normalized
