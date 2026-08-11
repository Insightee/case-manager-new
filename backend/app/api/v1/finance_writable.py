"""Finance writable Loop 2 — correction proposals, deductions, structured notes."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.feature_flags import require_billing_ledger_writes, require_finance_writable
from app.models.user import User
from app.services import (
    case_finance_note_service,
    finance_correction_service,
    finance_payout_deduction_service,
    therapist_invoice_case_line_service,
)

router = APIRouter(
    prefix="/admin/finance-writable",
    tags=["finance-writable"],
)


class CorrectResharePreviewBody(BaseModel):
    case_id: int
    billing_month: str
    wrong_side: str = Field(..., description="INVOICE_WRONG or RECORD_WRONG")


class CorrectReshareCreateBody(CorrectResharePreviewBody):
    reason: str = Field(..., min_length=1)
    billing_dispute_id: Optional[int] = None


class LinkedAmountEditBody(BaseModel):
    case_id: int
    billing_month: str
    new_client_amount_inr: float
    reason: str = Field(..., min_length=1)


class PayoutOnlyEditBody(BaseModel):
    case_id: int
    billing_month: str
    new_payout_amount_inr: float
    reason: str = Field(..., min_length=1)


class DeductionCreateBody(BaseModel):
    case_id: int
    billing_month: str
    therapist_user_id: int
    amount_inr: float = Field(..., gt=0)
    direction: str = Field(..., description="ADD or DEDUCT")
    reason: str = Field(..., min_length=1)
    note_type: str = Field(default="DEDUCTION")
    therapist_invoice_id: Optional[int] = None


class DeductionReverseBody(BaseModel):
    reversal_reason: str = Field(..., min_length=1)


class FinanceNoteCreateBody(BaseModel):
    case_id: int
    note_scope: str = Field(..., description="CRM, HR, or FINANCE")
    note_type: str = Field(default="OTHER")
    reason: str = Field(..., min_length=1)
    billing_month: Optional[str] = None
    amount_inr: Optional[float] = None


def _value_error(exc: ValueError) -> HTTPException:
    return HTTPException(status_code=400, detail=str(exc))


@router.post("/corrections/preview-correct-reshare")
def preview_correct_reshare(
    body: CorrectResharePreviewBody,
    user: User = Depends(require_finance_writable()),
    db: Session = Depends(get_db),
):
    _ = user
    try:
        return finance_correction_service.preview_correct_reshare(
            db,
            case_id=body.case_id,
            billing_month=body.billing_month,
            wrong_side=body.wrong_side,
        )
    except ValueError as exc:
        raise _value_error(exc) from exc


@router.post("/corrections/correct-reshare")
def create_correct_reshare(
    body: CorrectReshareCreateBody,
    user: User = Depends(require_finance_writable()),
    db: Session = Depends(get_db),
):
    require_billing_ledger_writes()
    try:
        result = finance_correction_service.create_correct_reshare_proposal(
            db,
            case_id=body.case_id,
            billing_month=body.billing_month,
            wrong_side=body.wrong_side,
            reason=body.reason,
            user_id=user.id,
            billing_dispute_id=body.billing_dispute_id,
        )
        db.commit()
        return result
    except ValueError as exc:
        db.rollback()
        raise _value_error(exc) from exc


@router.post("/corrections/linked-amount-edit")
def create_linked_amount_edit(
    body: LinkedAmountEditBody,
    user: User = Depends(require_finance_writable()),
    db: Session = Depends(get_db),
):
    require_billing_ledger_writes()
    try:
        result = finance_correction_service.create_linked_amount_edit_proposal(
            db,
            case_id=body.case_id,
            billing_month=body.billing_month,
            new_client_amount_inr=body.new_client_amount_inr,
            reason=body.reason,
            user_id=user.id,
        )
        db.commit()
        return result
    except ValueError as exc:
        db.rollback()
        raise _value_error(exc) from exc


@router.post("/corrections/payout-only-edit")
def create_payout_only_edit(
    body: PayoutOnlyEditBody,
    user: User = Depends(require_finance_writable()),
    db: Session = Depends(get_db),
):
    require_billing_ledger_writes()
    try:
        result = finance_correction_service.create_payout_only_edit_proposal(
            db,
            case_id=body.case_id,
            billing_month=body.billing_month,
            new_payout_amount_inr=body.new_payout_amount_inr,
            reason=body.reason,
            user_id=user.id,
        )
        db.commit()
        return result
    except ValueError as exc:
        db.rollback()
        raise _value_error(exc) from exc


@router.post("/corrections/{proposal_id}/approve")
def approve_correction(
    proposal_id: int,
    user: User = Depends(require_finance_writable()),
    db: Session = Depends(get_db),
):
    require_billing_ledger_writes()
    try:
        result = finance_correction_service.approve_proposal(db, proposal_id=proposal_id, user_id=user.id)
        db.commit()
        return result
    except ValueError as exc:
        db.rollback()
        raise _value_error(exc) from exc


@router.post("/corrections/{proposal_id}/reject")
def reject_correction(
    proposal_id: int,
    user: User = Depends(require_finance_writable()),
    db: Session = Depends(get_db),
):
    try:
        result = finance_correction_service.reject_proposal(db, proposal_id=proposal_id, user_id=user.id)
        db.commit()
        return result
    except ValueError as exc:
        db.rollback()
        raise _value_error(exc) from exc


@router.get("/corrections")
def list_corrections(
    case_id: Optional[int] = None,
    billing_month: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    user: User = Depends(require_finance_writable()),
    db: Session = Depends(get_db),
):
    _ = user
    return finance_correction_service.list_proposals(
        db, case_id=case_id, billing_month=billing_month, status=status, limit=limit
    )


@router.get("/corrections/{proposal_id}")
def get_correction(
    proposal_id: int,
    user: User = Depends(require_finance_writable()),
    db: Session = Depends(get_db),
):
    _ = user
    result = finance_correction_service.get_proposal(db, proposal_id)
    if not result:
        raise HTTPException(status_code=404, detail="Proposal not found")
    return result


@router.get("/deductions")
def list_deductions(
    case_id: int,
    billing_month: str,
    include_reversed: bool = False,
    user: User = Depends(require_finance_writable()),
    db: Session = Depends(get_db),
):
    _ = user
    items = finance_payout_deduction_service.list_deductions(
        db, case_id=case_id, billing_month=billing_month, include_reversed=include_reversed
    )
    gross = therapist_invoice_case_line_service.resolve_case_payout_gross_inr(
        db,
        case_id=case_id,
        billing_month=billing_month,
        therapist_user_id=items[0]["therapistUserId"] if items else None,
    )
    ladder = finance_payout_deduction_service.compute_payout_ladder(gross_inr=gross, deductions=items)
    return {"items": items, "payoutLadder": ladder, "order": "Gross → TDS → deductions → Net"}


@router.post("/deductions")
def create_deduction(
    body: DeductionCreateBody,
    user: User = Depends(require_finance_writable()),
    db: Session = Depends(get_db),
):
    require_billing_ledger_writes()
    try:
        result = finance_payout_deduction_service.create_deduction(
            db,
            case_id=body.case_id,
            billing_month=body.billing_month,
            therapist_user_id=body.therapist_user_id,
            amount_inr=body.amount_inr,
            direction=body.direction,
            reason=body.reason,
            note_type=body.note_type,
            therapist_invoice_id=body.therapist_invoice_id,
            user_id=user.id,
        )
        db.commit()
        return result
    except ValueError as exc:
        db.rollback()
        raise _value_error(exc) from exc


@router.post("/deductions/{deduction_id}/reverse")
def reverse_deduction(
    deduction_id: int,
    body: DeductionReverseBody,
    user: User = Depends(require_finance_writable()),
    db: Session = Depends(get_db),
):
    require_billing_ledger_writes()
    try:
        result = finance_payout_deduction_service.reverse_deduction(
            db, deduction_id=deduction_id, reversal_reason=body.reversal_reason, user_id=user.id
        )
        db.commit()
        return result
    except ValueError as exc:
        db.rollback()
        raise _value_error(exc) from exc


@router.get("/notes")
def list_notes(
    case_id: int,
    billing_month: Optional[str] = None,
    scope: Optional[str] = None,
    user: User = Depends(require_finance_writable()),
    db: Session = Depends(get_db),
):
    _ = user
    return case_finance_note_service.list_notes_for_case(
        db, case_id=case_id, billing_month=billing_month, scope=scope
    )


@router.post("/notes")
def create_note(
    body: FinanceNoteCreateBody,
    user: User = Depends(require_finance_writable()),
    db: Session = Depends(get_db),
):
    try:
        result = case_finance_note_service.create_note(
            db,
            case_id=body.case_id,
            note_scope=body.note_scope,
            note_type=body.note_type,
            reason=body.reason,
            user_id=user.id,
            billing_month=body.billing_month,
            amount_inr=body.amount_inr,
        )
        db.commit()
        return result
    except ValueError as exc:
        db.rollback()
        raise _value_error(exc) from exc
