"""Structured payout-side deductions — applied after TDS (Gross → TDS → deductions → Net)."""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.audit import log_audit
from app.models.finance_writable import (
    CaseFinanceNote,
    CaseFinanceNoteScope,
    CaseFinanceNoteType,
    FinancePayoutDeduction,
    FinancePayoutDeductionDirection,
    FinancePayoutDeductionStatus,
)
from app.services import billing_composer_service, therapist_invoice_case_line_service


def default_tds_rate_percent() -> float:
    raw = os.environ.get("FINANCE_DEFAULT_TDS_RATE_PERCENT", "10")
    try:
        return max(0.0, float(raw))
    except ValueError:
        return 10.0


def compute_payout_ladder(
    *,
    gross_inr: float,
    tds_rate_percent: float | None = None,
    deductions: list[dict[str, Any]] | None = None,
) -> dict[str, float]:
    """August-sheet order: Gross → TDS → deductions → Net."""
    rate = default_tds_rate_percent() if tds_rate_percent is None else float(tds_rate_percent)
    gross = round(float(gross_inr), 2)
    tds = round(gross * rate / 100.0, 2)
    after_tds = round(gross - tds, 2)

    deduct_total = 0.0
    add_total = 0.0
    for d in deductions or []:
        if d.get("status") == FinancePayoutDeductionStatus.REVERSED.value:
            continue
        amt = round(float(d.get("amountInr") or d.get("amount_inr") or 0), 2)
        if d.get("direction") in (FinancePayoutDeductionDirection.DEDUCT.value, "DEDUCT"):
            deduct_total += amt
        else:
            add_total += amt

    net = round(after_tds - deduct_total + add_total, 2)
    if net < 0:
        net = 0.0
    blocked = deduct_total > after_tds + 0.001
    return {
        "grossInr": gross,
        "tdsRatePercent": rate,
        "tdsInr": tds,
        "afterTdsInr": after_tds,
        "deductionsInr": round(deduct_total, 2),
        "additionsInr": round(add_total, 2),
        "netInr": net,
        "blocked": blocked,
        "blockReason": "Deduction exceeds payout after TDS — needs review" if blocked else None,
    }


def _deduction_dict(d: FinancePayoutDeduction) -> dict[str, Any]:
    return {
        "id": d.id,
        "caseId": d.case_id,
        "billingMonth": d.billing_month,
        "therapistUserId": d.therapist_user_id,
        "therapistInvoiceId": d.therapist_invoice_id,
        "amountInr": float(d.amount_inr),
        "direction": d.direction.value,
        "reason": d.reason,
        "noteType": d.note_type.value,
        "status": d.status.value,
        "createdByUserId": d.created_by_user_id,
        "createdAt": d.created_at.isoformat() if d.created_at else None,
        "reversedAt": d.reversed_at.isoformat() if d.reversed_at else None,
        "reversalReason": d.reversal_reason,
    }


def list_deductions(
    db: Session,
    *,
    case_id: int,
    billing_month: str,
    include_reversed: bool = False,
) -> list[dict[str, Any]]:
    ym = billing_composer_service.normalize_billing_month(billing_month)
    stmt = select(FinancePayoutDeduction).where(
        FinancePayoutDeduction.case_id == case_id,
        FinancePayoutDeduction.billing_month == ym,
    )
    if not include_reversed:
        stmt = stmt.where(FinancePayoutDeduction.status == FinancePayoutDeductionStatus.ACTIVE)
    rows = db.scalars(stmt.order_by(FinancePayoutDeduction.id)).all()
    return [_deduction_dict(r) for r in rows]


def create_deduction(
    db: Session,
    *,
    case_id: int,
    billing_month: str,
    therapist_user_id: int,
    amount_inr: float,
    direction: str,
    reason: str,
    note_type: str,
    user_id: int,
    therapist_invoice_id: int | None = None,
    create_finance_note: bool = True,
) -> dict[str, Any]:
    reason = (reason or "").strip()
    if not reason:
        raise ValueError("A reason is required for each deduction.")
    ym = billing_composer_service.normalize_billing_month(billing_month)
    gross = therapist_invoice_case_line_service.resolve_case_payout_gross_inr(
        db, case_id=case_id, billing_month=ym, therapist_user_id=therapist_user_id
    )
    existing = list_deductions(db, case_id=case_id, billing_month=ym, include_reversed=False)
    prospective = [
        *existing,
        {
            "amountInr": round(float(amount_inr), 2),
            "direction": direction.upper(),
            "status": FinancePayoutDeductionStatus.ACTIVE.value,
        },
    ]
    ladder = compute_payout_ladder(gross_inr=gross, deductions=prospective)
    if direction.upper() == "DEDUCT" and ladder.get("blocked"):
        raise ValueError(ladder.get("blockReason") or "Deduction exceeds available payout")

    ded = FinancePayoutDeduction(
        case_id=case_id,
        billing_month=ym,
        therapist_user_id=therapist_user_id,
        therapist_invoice_id=therapist_invoice_id,
        amount_inr=round(float(amount_inr), 2),
        direction=FinancePayoutDeductionDirection(direction.upper()),
        reason=reason,
        note_type=CaseFinanceNoteType(note_type.upper()),
        created_by_user_id=user_id,
    )
    db.add(ded)
    db.flush()

    if create_finance_note:
        note = CaseFinanceNote(
            case_id=case_id,
            billing_month=ym,
            note_scope=CaseFinanceNoteScope.FINANCE,
            note_type=ded.note_type,
            reason=reason,
            amount_inr=ded.amount_inr,
            author_user_id=user_id,
            linked_deduction_id=ded.id,
        )
        db.add(note)

    log_audit(
        db,
        actor_user_id=user_id,
        action="finance_payout_deduction_created",
        entity_type="finance_payout_deduction",
        entity_id=ded.id,
        new_value=_deduction_dict(ded),
        case_id=case_id,
    )
    db.flush()
    return _deduction_dict(ded)


def reverse_deduction(
    db: Session,
    *,
    deduction_id: int,
    reversal_reason: str,
    user_id: int,
) -> dict[str, Any]:
    reversal_reason = (reversal_reason or "").strip()
    if not reversal_reason:
        raise ValueError("A reversal reason is required.")
    ded = db.get(FinancePayoutDeduction, deduction_id)
    if not ded:
        raise ValueError("Deduction not found")
    if ded.status == FinancePayoutDeductionStatus.REVERSED:
        raise ValueError("Deduction already reversed")
    old = _deduction_dict(ded)
    ded.status = FinancePayoutDeductionStatus.REVERSED
    ded.reversed_at = datetime.now(timezone.utc)
    ded.reversed_by_user_id = user_id
    ded.reversal_reason = reversal_reason
    db.flush()
    log_audit(
        db,
        actor_user_id=user_id,
        action="finance_payout_deduction_reversed",
        entity_type="finance_payout_deduction",
        entity_id=ded.id,
        old_value=old,
        new_value=_deduction_dict(ded),
        case_id=ded.case_id,
    )
    return _deduction_dict(ded)
