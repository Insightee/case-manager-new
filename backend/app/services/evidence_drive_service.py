"""Evidence Drive — case documents grouped with clinical link metadata."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.case_document import CaseDocument
from app.models.user import User
from app.services import case_document_service as doc_svc
from app.services import case_service


def _group_key(doc: CaseDocument) -> str:
    if doc.linked_goal_id:
        return "goal_linked"
    if doc.linked_strategy_id:
        return "strategy_linked"
    if doc.linked_report_id:
        return "report_linked"
    if doc.domain_key:
        return f"domain:{doc.domain_key}"
    return "general"


def build_evidence_drive(db: Session, user: User, case_id: int) -> dict[str, Any]:
    case = case_service.get_case(db, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    items = doc_svc.list_for_case(db, user, case_id)
    groups: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        doc = db.get(CaseDocument, item.id)
        key = _group_key(doc) if doc else "general"
        row = item.model_dump()
        if doc:
            row["linked_report_id"] = doc.linked_report_id
            row["linked_goal_id"] = doc.linked_goal_id
            row["linked_strategy_id"] = doc.linked_strategy_id
            row["domain_key"] = doc.domain_key
        groups.setdefault(key, []).append(row)

    return {
        "case_id": case_id,
        "total_documents": len(items),
        "groups": [{"group_key": k, "items": v} for k, v in sorted(groups.items())],
    }


def link_evidence(
    db: Session,
    user: User,
    case_id: int,
    *,
    document_id: int,
    linked_report_id: Optional[int] = None,
    linked_goal_id: Optional[int] = None,
    linked_strategy_id: Optional[int] = None,
    domain_key: Optional[str] = None,
) -> dict[str, Any]:
    doc = doc_svc.get_document_or_404(db, document_id)
    if doc.case_id != case_id:
        raise HTTPException(status_code=404, detail="Document not found")
    doc_svc.require_read(db, user, doc)

    if linked_report_id is not None:
        doc.linked_report_id = linked_report_id
    if linked_goal_id is not None:
        doc.linked_goal_id = linked_goal_id
    if linked_strategy_id is not None:
        doc.linked_strategy_id = linked_strategy_id
    if domain_key is not None:
        doc.domain_key = domain_key.strip() or None

    db.flush()
    detail = doc_svc._serialize_detail(db, user, doc)
    return detail.model_dump()
