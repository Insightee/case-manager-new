from __future__ import annotations

import re
from typing import Any

from app.core.service_access import ORG_CAPABILITY_IDS
from app.models.service_category import ServiceCategory

_SLUG_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_RESERVED_MODULE_IDS = frozenset(ORG_CAPABILITY_IDS)


def resolved_product_modules(cat: ServiceCategory) -> list[dict[str, str]]:
    """Product modules for cases/RBAC; default to single module using category id."""
    raw = cat.product_modules
    if isinstance(raw, list) and raw:
        out: list[dict[str, str]] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            mid = str(item.get("id") or "").strip().lower()
            label = str(item.get("label") or "").strip()
            if mid and label:
                out.append({"id": mid, "label": label})
        if out:
            return out
    return [{"id": cat.id, "label": cat.label}]


def normalize_product_modules_payload(
    modules: list[Any] | None,
    *,
    default_id: str,
    default_label: str,
) -> list[dict[str, str]]:
    if not modules:
        return [{"id": default_id, "label": default_label}]
    seen: set[str] = set()
    out: list[dict[str, str]] = []
    for item in modules:
        if hasattr(item, "id"):
            mid = str(item.id or "").strip().lower()
            label = str(item.label or "").strip()
        elif isinstance(item, dict):
            mid = str(item.get("id") or "").strip().lower()
            label = str(item.get("label") or "").strip()
        else:
            continue
        if not mid or not label:
            raise ValueError("Each product module requires an id and label")
        if not _SLUG_RE.match(mid):
            raise ValueError(
                f"Invalid module id '{mid}': use lowercase letters, numbers, and underscores"
            )
        if mid in _RESERVED_MODULE_IDS:
            raise ValueError(f"Module id '{mid}' is reserved for a built-in programme module")
        if mid in seen:
            raise ValueError(f"Duplicate product module id '{mid}'")
        seen.add(mid)
        out.append({"id": mid, "label": label})
    return out


def category_to_read_dict(cat: ServiceCategory) -> dict[str, Any]:
    pms = resolved_product_modules(cat)
    return {
        "id": cat.id,
        "label": cat.label,
        "description": cat.description or None,
        "sort_order": cat.sort_order,
        "is_active": cat.is_active,
        "access_group": getattr(cat, "access_group", None) or "Clinical",
        "product_modules": pms,
    }


def product_module_label_map(registry: dict) -> dict[str, str]:
    """Map case product_module id -> display label from registry."""
    labels: dict[str, str] = {}
    for mod in registry.values():
        labels[mod.id] = mod.label
        for pid in mod.case_product_modules:
            sub = registry.get(pid)
            labels[pid] = sub.label if sub else mod.label
    return labels
