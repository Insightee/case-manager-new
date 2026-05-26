"""Service-category-centric access grants (clinical scope) vs org capabilities."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

SERVICE_ID_ALIASES = {"shadow": "shadow_support"}

ORG_CAPABILITY_IDS = frozenset(
    {"billing", "people_admin", "hr_ops", "service_catalog_admin"}
)


def normalize_service_id(service_id: str) -> str:
    sid = str(service_id or "").strip().lower()
    return SERVICE_ID_ALIASES.get(sid, sid)


def _normalize_grant_entry(raw: Any) -> dict:
    if not isinstance(raw, dict):
        return {"enabled": False, "access": "view"}
    access = str(raw.get("access", "write")).lower()
    if access not in ("view", "write"):
        access = "write"
    return {"enabled": bool(raw.get("enabled", True)), "access": access}


def normalize_service_access_grants(
    grants: dict[str, Any] | None,
    *,
    service_ids: list[str] | None = None,
    view_only: bool = False,
) -> dict[str, dict]:
    out: dict[str, dict] = {}
    if grants:
        for mid, entry in grants.items():
            slug = normalize_service_id(mid)
            if slug:
                out[slug] = _normalize_grant_entry(entry)
    if not out and service_ids:
        access = "view" if view_only else "write"
        for mid in service_ids:
            slug = normalize_service_id(mid)
            if slug:
                out[slug] = {"enabled": True, "access": access}
    return out


def normalize_org_capability_grants(grants: dict[str, Any] | None) -> dict[str, dict]:
    out: dict[str, dict] = {}
    if not grants:
        return out
    for mid, entry in grants.items():
        slug = str(mid).strip().lower()
        if slug in ORG_CAPABILITY_IDS:
            out[slug] = _normalize_grant_entry(entry)
    return out


def active_service_category_ids(db: Session | None) -> set[str]:
    if db is None:
        from app.core.therapist_services import SERVICE_CATEGORIES

        return {normalize_service_id(s["id"]) for s in SERVICE_CATEGORIES}
    try:
        from app.models.service_category import ServiceCategory

        rows = db.scalars(
            select(ServiceCategory).where(ServiceCategory.is_active.is_(True))
        ).all()
        return {normalize_service_id(r.id) for r in rows}
    except Exception:
        return set()


def parent_service_id_for_product_module(db: Session | None, module_id: str) -> str | None:
    """Resolve a case product_module id to its parent service category id."""
    if db is None:
        return None
    try:
        from sqlalchemy import select

        from app.models.service_category import ServiceCategory
        from app.services.service_category_service import resolved_product_modules

        mid = normalize_service_id(module_id)
        for cat in db.scalars(select(ServiceCategory).where(ServiceCategory.is_active.is_(True))).all():
            for pm in resolved_product_modules(cat):
                if normalize_service_id(pm["id"]) == mid:
                    return normalize_service_id(cat.id)
    except Exception:
        return None
    return None


def legacy_module_assignments_to_service_grants(
  module_assignments: list[str] | None,
  module_access_grants: dict | None,
  *,
  db: Session | None,
  view_only: bool = False,
) -> dict[str, dict]:
    """Map legacy module_assignments / module_access_grants to service_access_grants."""
    valid = active_service_category_ids(db)
    org_ids = ORG_CAPABILITY_IDS | {"billing"}

    if module_access_grants:
        clinical: dict[str, Any] = {}
        for mid, entry in module_access_grants.items():
            slug = normalize_service_id(mid)
            if slug in org_ids:
                continue
            if slug in valid or slug in ("homecare", "shadow_support"):
                clinical[slug] = entry
        if clinical:
            return normalize_service_access_grants(clinical, view_only=view_only)

    out: dict[str, dict] = {}
    access = "view" if view_only else "write"
    for mid in module_assignments or []:
        slug = normalize_service_id(mid)
        if slug in org_ids:
            continue
        if slug in valid or slug in ("homecare", "shadow_support"):
            out[slug] = {"enabled": True, "access": access}
            continue
        parent = parent_service_id_for_product_module(db, slug)
        if parent:
            out[parent] = {"enabled": True, "access": access}
    return out


def service_grants_to_module_assignments(
    service_grants: dict[str, dict] | None,
    org_grants: dict[str, dict] | None,
) -> list[str]:
    """Dual-write legacy module_assignments for compatibility."""
    ids: list[str] = []
    for mid, g in (service_grants or {}).items():
        if g.get("enabled"):
            ids.append(normalize_service_id(mid))
    for mid, g in (org_grants or {}).items():
        if g.get("enabled"):
            ids.append(str(mid).strip().lower())
    return list(dict.fromkeys(ids))


def user_service_access_grant(user, service_id: str, db: Session | None = None) -> dict | None:
    from app.core.rbac_access import user_module_grant

    slug = normalize_service_id(service_id)
    grants = getattr(user, "service_access_grants", None) or {}
    if slug in grants:
        return _normalize_grant_entry(grants[slug])
    if grants:
        return None
    legacy = user_module_grant(user, slug)
    if legacy and slug in active_service_category_ids(db):
        return legacy
    return legacy


def user_has_service_access(user, service_id: str, *, write: bool = False, db: Session | None = None) -> bool:
    from app.core.module_access import module_bypass

    if module_bypass(user):
        return True
    grant = user_service_access_grant(user, service_id, db)
    if not grant or not grant.get("enabled"):
        return False
    if write and (getattr(user, "is_view_only", False) or grant.get("access") != "write"):
        return False
    return True


def sync_dual_access_fields(user, *, db: Session | None = None) -> None:
    """Keep module_assignments in sync after service/org grants are set."""
    svc = getattr(user, "service_access_grants", None) or {}
    org = getattr(user, "org_capability_grants", None) or {}
    if not svc and user.module_access_grants:
        svc = legacy_module_assignments_to_service_grants(
            user.module_assignments,
            user.module_access_grants,
            db=db,
            view_only=getattr(user, "is_view_only", False),
        )
        user.service_access_grants = svc
    user.module_assignments = service_grants_to_module_assignments(svc, org)
