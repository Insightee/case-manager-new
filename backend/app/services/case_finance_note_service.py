"""Structured CRM / HR / Finance notes for billing readiness master sheet."""
from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.audit import log_audit
from app.models.finance_writable import CaseFinanceNote, CaseFinanceNoteScope, CaseFinanceNoteType
from app.services import billing_composer_service


def _note_dict(n: CaseFinanceNote) -> dict[str, Any]:
    return {
        "id": n.id,
        "caseId": n.case_id,
        "billingMonth": n.billing_month,
        "noteScope": n.note_scope.value,
        "noteType": n.note_type.value,
        "reason": n.reason,
        "amountInr": float(n.amount_inr) if n.amount_inr is not None else None,
        "authorUserId": n.author_user_id,
        "linkedDeductionId": n.linked_deduction_id,
        "createdAt": n.created_at.isoformat() if n.created_at else None,
    }


def list_notes_for_case(
    db: Session,
    *,
    case_id: int,
    billing_month: str | None = None,
    scope: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    stmt = select(CaseFinanceNote).where(CaseFinanceNote.case_id == case_id)
    if billing_month:
        ym = billing_composer_service.normalize_billing_month(billing_month)
        stmt = stmt.where(
            (CaseFinanceNote.billing_month == ym) | (CaseFinanceNote.billing_month.is_(None))
        )
    if scope:
        stmt = stmt.where(CaseFinanceNote.note_scope == CaseFinanceNoteScope(scope.upper()))
    rows = db.scalars(stmt.order_by(CaseFinanceNote.created_at.desc()).limit(max(1, min(limit, 200)))).all()
    return [_note_dict(n) for n in rows]


def latest_notes_by_scope(
    db: Session,
    *,
    case_id: int,
    billing_month: str,
) -> dict[str, str]:
    """Compact strings for master sheet CRM/HR columns."""
    notes = list_notes_for_case(db, case_id=case_id, billing_month=billing_month, limit=20)
    out: dict[str, str] = {}
    for scope in (CaseFinanceNoteScope.CRM, CaseFinanceNoteScope.HR, CaseFinanceNoteScope.FINANCE):
        scoped = [n for n in notes if n["noteScope"] == scope.value]
        if not scoped:
            continue
        latest = scoped[0]
        label = f"{latest['noteType']}: {latest['reason']}"
        if latest.get("amountInr") is not None:
            label += f" (₹{latest['amountInr']:.2f})"
        out[scope.value.lower()] = label
    return out


def create_note(
    db: Session,
    *,
    case_id: int,
    note_scope: str,
    note_type: str,
    reason: str,
    user_id: int,
    billing_month: str | None = None,
    amount_inr: float | None = None,
) -> dict[str, Any]:
    reason = (reason or "").strip()
    if not reason:
        raise ValueError("A reason is required for structured notes.")
    ym = billing_composer_service.normalize_billing_month(billing_month) if billing_month else None
    note = CaseFinanceNote(
        case_id=case_id,
        billing_month=ym,
        note_scope=CaseFinanceNoteScope(note_scope.upper()),
        note_type=CaseFinanceNoteType(note_type.upper()),
        reason=reason,
        amount_inr=round(float(amount_inr), 2) if amount_inr is not None else None,
        author_user_id=user_id,
    )
    db.add(note)
    db.flush()
    log_audit(
        db,
        actor_user_id=user_id,
        action="case_finance_note_created",
        entity_type="case_finance_note",
        entity_id=note.id,
        new_value=_note_dict(note),
        case_id=case_id,
    )
    return _note_dict(note)
