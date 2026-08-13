from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.core.billing_validation import apply_billing_payload
from app.models.case import DAY_TYPE_PRODUCT_MODULES, Case, CaseDayType
from app.services import case_code_service


def product_requires_day_type(product_module: str | None) -> bool:
    normalized = case_code_service.normalize_product_module(product_module or "")
    return normalized in DAY_TYPE_PRODUCT_MODULES


def day_type_label(day_type: CaseDayType | str | None) -> str | None:
    if day_type is None:
        return None
    value = day_type.value if isinstance(day_type, CaseDayType) else str(day_type)
    if value == CaseDayType.HALF_DAY.value:
        return "Half day"
    if value == CaseDayType.FULL_DAY.value:
        return "Full day"
    return value.replace("_", " ").title()


def parse_day_type(raw: str | CaseDayType | None) -> CaseDayType | None:
    if raw is None:
        return None
    if isinstance(raw, CaseDayType):
        return raw
    normalized = str(raw).strip().upper()
    if not normalized:
        return None
    return CaseDayType(normalized)


def validate_allotment_day_type(product_module: str, day_type: CaseDayType | str | None) -> CaseDayType | None:
    parsed = parse_day_type(day_type)
    if product_requires_day_type(product_module):
        if parsed is None:
            raise ValueError("Half day or full day is required for shadow support and B2B cases.")
        return parsed
    if parsed is not None:
        raise ValueError("Day type applies to shadow support and B2B cases only.")
    return None


def update_case_day_type(
    db: Session,
    *,
    case: Case,
    actor_user_id: int,
    day_type: CaseDayType | str,
    reason: str | None = None,
    update_billing: bool = False,
    billing_update: dict[str, Any] | None = None,
) -> tuple[Case, dict[str, Any]]:
    if not product_requires_day_type(case.product_module):
        raise ValueError("Day type applies to shadow support and B2B cases only.")

    new_type = parse_day_type(day_type)
    if new_type is None:
        raise ValueError("Select half day or full day.")

    old_type = case.day_type
    if old_type == new_type:
        return case, {
            "changed": False,
            "old_day_type": old_type.value if old_type else None,
            "new_day_type": new_type.value,
            "reason": None,
            "billing_updated": False,
        }

    trimmed_reason = (reason or "").strip()
    if old_type is not None and len(trimmed_reason) < 5:
        raise ValueError("Please add a reason for changing day type (at least 5 characters).")

    billing_updated = False
    if update_billing:
        if not billing_update:
            raise ValueError("Update billing details before saving the day type change.")
        apply_billing_payload(case, billing_update, actor_user_id)
        billing_updated = True

    case.day_type = new_type
    db.flush()
    return case, {
        "changed": True,
        "old_day_type": old_type.value if old_type else None,
        "new_day_type": new_type.value,
        "reason": trimmed_reason or None,
        "billing_updated": billing_updated,
    }


def audit_detail_for_change(meta: dict[str, Any]) -> str:
    old_label = day_type_label(meta.get("old_day_type")) or "Not set"
    new_label = day_type_label(meta.get("new_day_type")) or "Not set"
    parts = [f"{old_label} → {new_label}"]
    if meta.get("reason"):
        parts.append(f"Reason: {meta['reason']}")
    if meta.get("billing_updated"):
        parts.append("Billing updated")
    return " · ".join(parts)
