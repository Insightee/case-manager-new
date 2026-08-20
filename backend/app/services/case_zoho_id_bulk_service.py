"""Bulk set cases.zoho_id from CSV rows (preview first, then apply)."""
from __future__ import annotations

from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.case import Case
from app.models.user import User
from app.services import case_service
from app.services.admin_scope_service import apply_case_scope

RowStatus = Literal["skipped", "unchanged", "will_update", "updated", "failed"]


def process_bulk_zoho_id_rows(
    db: Session,
    rows: list[dict],
    *,
    actor: User,
    apply: bool,
) -> dict:
    results: list[dict] = []
    seen_codes: dict[str, str] = {}
    summary = {"skipped": 0, "unchanged": 0, "will_update": 0, "updated": 0, "failed": 0}

    for index, row in enumerate(rows, start=1):
        case_code = case_service.normalize_case_code(row.get("case_code"))
        zoho_id = case_service.normalize_zoho_id(row.get("zoho_id"))
        base = {
            "row_index": index,
            "case_code": case_code,
            "zoho_id": zoho_id,
            "old_zoho_id": None,
            "warning": None,
            "message": None,
        }

        if not case_code or not zoho_id:
            missing = []
            if not case_code:
                missing.append("case code")
            if not zoho_id:
                missing.append("Zoho ID")
            results.append(
                {
                    **base,
                    "status": "skipped",
                    "message": f"Skipped — missing {' and '.join(missing)}",
                }
            )
            summary["skipped"] += 1
            continue

        prior = seen_codes.get(case_code)
        if prior is not None:
            if prior == zoho_id:
                results.append(
                    {
                        **base,
                        "status": "skipped",
                        "message": "Duplicate row — this case already appears in this upload",
                    }
                )
                summary["skipped"] += 1
            else:
                results.append(
                    {
                        **base,
                        "status": "failed",
                        "message": f"Conflicting Zoho IDs for {case_code} in this upload ({prior} vs {zoho_id})",
                    }
                )
                summary["failed"] += 1
            continue
        seen_codes[case_code] = zoho_id

        stmt = apply_case_scope(select(Case).where(func.upper(Case.case_code) == case_code), actor)
        case = db.scalars(stmt).first()
        if not case:
            exists = db.scalars(select(Case.id).where(func.upper(Case.case_code) == case_code)).first()
            message = (
                "This case is outside your access"
                if exists
                else f"Case not found: {case_code}"
            )
            results.append({**base, "status": "failed", "message": message})
            summary["failed"] += 1
            continue

        current = case_service.normalize_zoho_id(case.zoho_id)
        base["old_zoho_id"] = current
        if current == zoho_id:
            results.append(
                {
                    **base,
                    "status": "unchanged",
                    "message": "Already has this Zoho ID",
                }
            )
            summary["unchanged"] += 1
            continue

        warning = None
        if current:
            warning = f"Will replace existing Zoho ID {current}"

        if apply:
            case.zoho_id = zoho_id
            results.append(
                {
                    **base,
                    "status": "updated",
                    "message": "Zoho ID saved",
                    "warning": warning,
                }
            )
            summary["updated"] += 1
        else:
            results.append(
                {
                    **base,
                    "status": "will_update",
                    "message": "Ready to save",
                    "warning": warning,
                }
            )
            summary["will_update"] += 1

    return {"summary": summary, "results": results}
