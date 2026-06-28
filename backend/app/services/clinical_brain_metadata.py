"""Parse/serialize repository metadata_json for Clinical Brain bank/pool fields."""

from __future__ import annotations

import json
from typing import Any


def parse_metadata(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}


def dump_metadata(data: dict[str, Any] | None) -> str | None:
    if not data:
        return None
    cleaned = {k: v for k, v in data.items() if v is not None and v != ""}
    return json.dumps(cleaned) if cleaned else None


def merge_metadata(existing: str | None, patch: dict[str, Any]) -> str | None:
    base = parse_metadata(existing)
    base.update({k: v for k, v in patch.items() if v is not None})
    return dump_metadata(base)


def derive_review_status(
    *,
    status: str | None,
    lifecycle_status: str | None,
    review_note: str | None,
    scope: str | None,
    case_id: int | None,
) -> str:
    st = (status or "local").lower()
    life = (lifecycle_status or "").lower()
    if st == "archived":
        return "deprecated"
    if review_note and st in ("candidate", "local"):
        return "returned_with_comments"
    if life == "pending_review" or (st == "candidate" and case_id is not None):
        return "pending_cm_review"
    if st in ("approved", "active") and case_id is None and scope in ("organization", "org", None):
        return "pool_active"
    if st in ("approved", "active") and case_id is not None:
        return "approved_for_case"
    if st == "local":
        return "draft"
    if st == "candidate":
        return "case_candidate"
    return "draft"


def evidence_label_from_uses(total: int) -> str:
    if total >= 5:
        return "commonly_used"
    if total >= 2:
        return "emerging"
    if total == 1:
        return "used_once"
    return "new"
