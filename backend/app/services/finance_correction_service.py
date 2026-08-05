"""Finance correction proposals — correct-and-reshare, linked client↔payout edits.

Money loop: every change is a PROPOSAL until a human approves. Engine is SSOT;
edits route through this service, never free-field mutation.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.audit import log_audit
from app.models.case import BillingType, Case
from app.models.client_billing import ClientInvoice, ClientInvoiceStatus
from app.models.finance_writable import (
    FinanceCorrectionProposal,
    FinanceCorrectionProposalType,
    FinanceProposalStatus,
    FinanceWrongSide,
)
from app.models.invoice import Invoice
from app.models.invoice_line import InvoiceCaseLine
from app.models.ledger_billing import BillingLedger, BillableStatus, LedgerEventType, LedgerSourceType
from app.services import billing_composer_service, finance_payout_preview_service


def _now() -> datetime:
    return datetime.now(timezone.utc)


def case_client_billing_inr(case: Case) -> float | None:
    """Client billing base from case agreement (monthly, package, or per-session rate)."""
    if case.billing_type == BillingType.MONTHLY_FIXED and case.client_monthly_rate_inr is not None:
        return round(float(case.client_monthly_rate_inr), 2)
    if case.billing_type == BillingType.PACKAGE and case.package_amount_inr is not None:
        return round(float(case.package_amount_inr), 2)
    if case.client_rate_per_session_inr is not None:
        return round(float(case.client_rate_per_session_inr), 2)
    return None


def case_share_ratio(case: Case) -> float | None:
    """Therapist share / client billing from case record. None → block, never guess."""
    therapist = finance_payout_preview_service.therapist_share_inr(case)
    client = case_client_billing_inr(case)
    if therapist <= 0 or client is None or client <= 0:
        return None
    return round(therapist / client, 8)


def payout_from_client_amount(client_amount_inr: float, ratio: float) -> float:
    return round(float(client_amount_inr) * float(ratio), 2)


def _find_client_invoice(db: Session, *, case_id: int, billing_month: str) -> ClientInvoice | None:
    ym = billing_composer_service.normalize_billing_month(billing_month)
    return db.scalars(
        select(ClientInvoice)
        .where(ClientInvoice.case_id == case_id, ClientInvoice.billing_month == ym)
        .order_by(ClientInvoice.id.desc())
        .limit(1)
    ).first()


def _find_therapist_invoice_for_case(
    db: Session, *, case_id: int, billing_month: str
) -> tuple[Invoice | None, InvoiceCaseLine | None]:
    ym = billing_composer_service.normalize_billing_month(billing_month)
    row = db.scalars(
        select(InvoiceCaseLine)
        .join(Invoice, InvoiceCaseLine.invoice_id == Invoice.id)
        .where(InvoiceCaseLine.case_id == case_id, Invoice.month == ym)
        .order_by(Invoice.id.desc())
        .limit(1)
    ).first()
    if not row:
        return None, None
    inv = db.get(Invoice, row.invoice_id)
    return inv, row


def _current_payout_inr(db: Session, *, case_id: int, billing_month: str) -> float:
    _, case_line = _find_therapist_invoice_for_case(db, case_id=case_id, billing_month=billing_month)
    if case_line:
        return round(float(case_line.therapist_share_inr or 0), 2)
    return 0.0


def _proposal_dict(p: FinanceCorrectionProposal) -> dict[str, Any]:
    return {
        "id": p.id,
        "caseId": p.case_id,
        "billingMonth": p.billing_month,
        "clientInvoiceId": p.client_invoice_id,
        "therapistInvoiceId": p.therapist_invoice_id,
        "proposalType": p.proposal_type.value,
        "wrongSide": p.wrong_side.value if p.wrong_side else None,
        "status": p.status.value,
        "reason": p.reason,
        "oldClientAmountInr": float(p.old_client_amount_inr) if p.old_client_amount_inr is not None else None,
        "newClientAmountInr": float(p.new_client_amount_inr) if p.new_client_amount_inr is not None else None,
        "oldPayoutAmountInr": float(p.old_payout_amount_inr) if p.old_payout_amount_inr is not None else None,
        "newPayoutAmountInr": float(p.new_payout_amount_inr) if p.new_payout_amount_inr is not None else None,
        "caseShareRatio": float(p.case_share_ratio) if p.case_share_ratio is not None else None,
        "recordCorrectionPayload": p.record_correction_payload,
        "createdByUserId": p.created_by_user_id,
        "reviewedByUserId": p.reviewed_by_user_id,
        "createdAt": p.created_at.isoformat() if p.created_at else None,
        "reviewedAt": p.reviewed_at.isoformat() if p.reviewed_at else None,
        "confirmScreen": {
            "oldClientAmountInr": float(p.old_client_amount_inr) if p.old_client_amount_inr is not None else None,
            "newClientAmountInr": float(p.new_client_amount_inr) if p.new_client_amount_inr is not None else None,
            "oldPayoutAmountInr": float(p.old_payout_amount_inr) if p.old_payout_amount_inr is not None else None,
            "newPayoutAmountInr": float(p.new_payout_amount_inr) if p.new_payout_amount_inr is not None else None,
            "reasonRequired": True,
        },
    }


def preview_correct_reshare(
    db: Session,
    *,
    case_id: int,
    billing_month: str,
    wrong_side: str,
) -> dict[str, Any]:
    """Preview a correct-and-reshare correction without persisting."""
    case = db.get(Case, case_id)
    if not case:
        raise ValueError("Case not found")
    side = FinanceWrongSide(wrong_side.upper())
    ym = billing_composer_service.normalize_billing_month(billing_month)
    inv = _find_client_invoice(db, case_id=case_id, billing_month=ym)
    preview = billing_composer_service.get_composer_preview(db, case_id=case_id, billing_month=ym)
    engine_amount = preview.get("overview", {}).get("total")
    engine_amount = round(float(engine_amount), 2) if engine_amount is not None else None

    old_client = round(float(inv.total_inr or 0), 2) if inv else None
    old_payout = _current_payout_inr(db, case_id=case_id, billing_month=ym)

    ratio = case_share_ratio(case)
    if side == FinanceWrongSide.INVOICE_WRONG:
        if engine_amount is None:
            raise ValueError("Engine amount unavailable — cannot correct invoice to activity")
        new_client = engine_amount
        new_payout = payout_from_client_amount(new_client, ratio) if ratio is not None else None
    else:
        new_client = old_client
        new_payout = old_payout

    blocked = ratio is None and side == FinanceWrongSide.INVOICE_WRONG
    return {
        "wrongSide": side.value,
        "oldClientAmountInr": old_client,
        "newClientAmountInr": new_client,
        "oldPayoutAmountInr": old_payout,
        "newPayoutAmountInr": new_payout,
        "caseShareRatio": ratio,
        "engineAmountInr": engine_amount,
        "blocked": blocked,
        "blockReason": "Case share ratio unavailable — needs review, cannot guess payout" if blocked else None,
        "confirmScreen": {
            "oldClientAmountInr": old_client,
            "newClientAmountInr": new_client,
            "oldPayoutAmountInr": old_payout,
            "newPayoutAmountInr": new_payout,
            "reasonRequired": True,
        },
    }


def create_correct_reshare_proposal(
    db: Session,
    *,
    case_id: int,
    billing_month: str,
    wrong_side: str,
    reason: str,
    user_id: int,
) -> dict[str, Any]:
    reason = (reason or "").strip()
    if not reason:
        raise ValueError("A reason is required before we can save this correction proposal.")
    case = db.get(Case, case_id)
    if not case:
        raise ValueError("Case not found")
    side = FinanceWrongSide(wrong_side.upper())
    preview = preview_correct_reshare(db, case_id=case_id, billing_month=billing_month, wrong_side=side.value)
    if preview.get("blocked"):
        raise ValueError(preview.get("blockReason") or "Correction blocked — share ratio missing")

    ym = billing_composer_service.normalize_billing_month(billing_month)
    inv = _find_client_invoice(db, case_id=case_id, billing_month=ym)
    therapist_inv, _ = _find_therapist_invoice_for_case(db, case_id=case_id, billing_month=ym)
    ratio = preview.get("caseShareRatio")

    payload: dict[str, Any] | None = None
    if side == FinanceWrongSide.RECORD_WRONG:
        payload = {
            "targetSessionCount": preview.get("engineAmountInr"),
            "raisedInvoiceAmountInr": preview.get("oldClientAmountInr"),
            "engineAmountInr": preview.get("engineAmountInr"),
        }

    status = FinanceProposalStatus.PENDING
    if ratio is None and side == FinanceWrongSide.INVOICE_WRONG:
        status = FinanceProposalStatus.NEEDS_REVIEW

    proposal = FinanceCorrectionProposal(
        case_id=case_id,
        billing_month=ym,
        client_invoice_id=inv.id if inv else None,
        therapist_invoice_id=therapist_inv.id if therapist_inv else None,
        proposal_type=FinanceCorrectionProposalType.CORRECT_RESHARE,
        wrong_side=side,
        status=status,
        reason=reason,
        old_client_amount_inr=preview.get("oldClientAmountInr"),
        new_client_amount_inr=preview.get("newClientAmountInr"),
        old_payout_amount_inr=preview.get("oldPayoutAmountInr"),
        new_payout_amount_inr=preview.get("newPayoutAmountInr"),
        case_share_ratio=ratio,
        record_correction_payload=payload,
        created_by_user_id=user_id,
    )
    db.add(proposal)
    db.flush()
    log_audit(
        db,
        actor_user_id=user_id,
        action="finance_correction_proposed",
        entity_type="finance_correction_proposal",
        entity_id=proposal.id,
        new_value=_proposal_dict(proposal),
        case_id=case_id,
    )
    return _proposal_dict(proposal)


def create_linked_amount_edit_proposal(
    db: Session,
    *,
    case_id: int,
    billing_month: str,
    new_client_amount_inr: float,
    reason: str,
    user_id: int,
) -> dict[str, Any]:
    reason = (reason or "").strip()
    if not reason:
        raise ValueError("A reason is required before we can save this linked edit proposal.")
    case = db.get(Case, case_id)
    if not case:
        raise ValueError("Case not found")
    ratio = case_share_ratio(case)
    if ratio is None:
        raise ValueError("Case share ratio unavailable — needs review, cannot guess payout")

    ym = billing_composer_service.normalize_billing_month(billing_month)
    inv = _find_client_invoice(db, case_id=case_id, billing_month=ym)
    if not inv:
        raise ValueError("No client invoice for this case-month")
    therapist_inv, _ = _find_therapist_invoice_for_case(db, case_id=case_id, billing_month=ym)

    old_client = round(float(inv.total_inr or 0), 2)
    old_payout = _current_payout_inr(db, case_id=case_id, billing_month=ym)
    new_client = round(float(new_client_amount_inr), 2)
    new_payout = payout_from_client_amount(new_client, ratio)

    proposal = FinanceCorrectionProposal(
        case_id=case_id,
        billing_month=ym,
        client_invoice_id=inv.id,
        therapist_invoice_id=therapist_inv.id if therapist_inv else None,
        proposal_type=FinanceCorrectionProposalType.LINKED_AMOUNT_EDIT,
        wrong_side=None,
        status=FinanceProposalStatus.PENDING,
        reason=reason,
        old_client_amount_inr=old_client,
        new_client_amount_inr=new_client,
        old_payout_amount_inr=old_payout,
        new_payout_amount_inr=new_payout,
        case_share_ratio=ratio,
        created_by_user_id=user_id,
    )
    db.add(proposal)
    db.flush()
    log_audit(
        db,
        actor_user_id=user_id,
        action="finance_linked_edit_proposed",
        entity_type="finance_correction_proposal",
        entity_id=proposal.id,
        new_value=_proposal_dict(proposal),
        case_id=case_id,
    )
    return _proposal_dict(proposal)


def create_payout_only_edit_proposal(
    db: Session,
    *,
    case_id: int,
    billing_month: str,
    new_payout_amount_inr: float,
    reason: str,
    user_id: int,
) -> dict[str, Any]:
    """Separate path — payout-only edit, visually distinct from linked client edit."""
    reason = (reason or "").strip()
    if not reason:
        raise ValueError("A reason is required before we can save this payout edit proposal.")
    case = db.get(Case, case_id)
    if not case:
        raise ValueError("Case not found")

    ym = billing_composer_service.normalize_billing_month(billing_month)
    inv = _find_client_invoice(db, case_id=case_id, billing_month=ym)
    therapist_inv, _ = _find_therapist_invoice_for_case(db, case_id=case_id, billing_month=ym)
    if not therapist_inv:
        raise ValueError("No therapist invoice for this case-month")

    old_payout = _current_payout_inr(db, case_id=case_id, billing_month=ym)
    old_client = round(float(inv.total_inr or 0), 2) if inv else None
    new_payout = round(float(new_payout_amount_inr), 2)

    proposal = FinanceCorrectionProposal(
        case_id=case_id,
        billing_month=ym,
        client_invoice_id=inv.id if inv else None,
        therapist_invoice_id=therapist_inv.id,
        proposal_type=FinanceCorrectionProposalType.PAYOUT_ONLY_EDIT,
        wrong_side=None,
        status=FinanceProposalStatus.PENDING,
        reason=reason,
        old_client_amount_inr=old_client,
        new_client_amount_inr=old_client,
        old_payout_amount_inr=old_payout,
        new_payout_amount_inr=new_payout,
        case_share_ratio=None,
        created_by_user_id=user_id,
    )
    db.add(proposal)
    db.flush()
    log_audit(
        db,
        actor_user_id=user_id,
        action="finance_payout_only_edit_proposed",
        entity_type="finance_correction_proposal",
        entity_id=proposal.id,
        new_value=_proposal_dict(proposal),
        case_id=case_id,
    )
    return _proposal_dict(proposal)


def _apply_client_correction(
    db: Session,
    *,
    inv: ClientInvoice,
    new_total_inr: float,
    reason: str,
    user_id: int,
) -> dict[str, Any]:
    old_total = round(float(inv.total_inr or 0), 2)
    delta = round(new_total_inr - old_total, 2)
    inv.adjustment_inr = round(float(inv.adjustment_inr or 0) + delta, 2)
    inv.total_inr = round(new_total_inr, 2)
    snap = dict(inv.billing_snapshot or {})
    snap["financeCorrectionReason"] = reason
    snap["financeCorrectionAt"] = _now().isoformat()
    snap["financeCorrectionByUserId"] = user_id
    inv.billing_snapshot = snap
    db.flush()
    return {"oldTotalInr": old_total, "newTotalInr": new_total_inr, "adjustmentDeltaInr": delta}


def _apply_payout_correction(
    db: Session,
    *,
    case_id: int,
    billing_month: str,
    new_payout_inr: float,
    reason: str,
    user_id: int,
) -> dict[str, Any]:
    therapist_inv, case_line = _find_therapist_invoice_for_case(
        db, case_id=case_id, billing_month=billing_month
    )
    if not therapist_inv or not case_line:
        raise ValueError("Therapist invoice case line not found for payout correction")

    old_payout = round(float(case_line.therapist_share_inr or 0), 2)
    case_line.therapist_share_inr = round(new_payout_inr, 2)
    snap = dict(case_line.billing_snapshot or {})
    snap["financeCorrectionReason"] = reason
    snap["financeCorrectionAt"] = _now().isoformat()
    snap["financeCorrectionByUserId"] = user_id
    case_line.billing_snapshot = snap

    all_lines = db.scalars(
        select(InvoiceCaseLine).where(InvoiceCaseLine.invoice_id == therapist_inv.id)
    ).all()
    new_invoice_total = round(sum(float(cl.therapist_share_inr or 0) for cl in all_lines), 2)
    old_invoice_amount = round(float(therapist_inv.amount_inr or 0), 2)
    therapist_inv.amount_inr = new_invoice_total
    therapist_inv.subtotal_inr = new_invoice_total
    notes = (therapist_inv.notes or "").strip()
    therapist_inv.notes = f"{notes}\n[Finance correction] {reason}".strip()
    db.flush()
    return {
        "oldPayoutInr": old_payout,
        "newPayoutInr": new_payout_inr,
        "oldInvoiceAmountInr": old_invoice_amount,
        "newInvoiceAmountInr": new_invoice_total,
    }


def _apply_record_correction(
    db: Session,
    *,
    case_id: int,
    billing_month: str,
    payload: dict[str, Any] | None,
    reason: str,
    user_id: int,
) -> dict[str, Any]:
    """Correct activity/ledger — invoice stands."""
    ym = billing_composer_service.normalize_billing_month(billing_month)
    target_amount = payload.get("raisedInvoiceAmountInr") if payload else None
    if target_amount is None:
        raise ValueError("Record correction payload missing target amount")

    rows = db.scalars(
        select(BillingLedger).where(
            BillingLedger.case_id == case_id,
            BillingLedger.ledger_month == ym,
        )
    ).all()
    current_billable = round(
        sum(float(r.total_inr or 0) for r in rows if r.billable_status != BillableStatus.NON_BILLABLE),
        2,
    )
    delta = round(float(target_amount) - current_billable, 2)
    if abs(delta) < 0.01:
        return {"ledgerAdjustmentInr": 0, "message": "Ledger already matches invoice"}

    adj = BillingLedger(
        case_id=case_id,
        ledger_month=ym,
        event_date=_now().date(),
        event_type=LedgerEventType.MANUAL_ADJUSTMENT,
        source_type=LedgerSourceType.MANUAL,
        billable_status=BillableStatus.BILLABLE,
        quantity=1,
        rate_inr=delta,
        amount_inr=delta,
        total_inr=delta,
        admin_note=f"Finance record correction: {reason}",
        override_reason=reason,
        overridden_by_user_id=user_id,
    )
    db.add(adj)
    db.flush()
    return {"ledgerAdjustmentInr": delta, "ledgerRowId": adj.id}


def approve_proposal(db: Session, *, proposal_id: int, user_id: int) -> dict[str, Any]:
    """Atomic approve — client + payout both commit or neither."""
    proposal = db.get(FinanceCorrectionProposal, proposal_id)
    if not proposal:
        raise ValueError("Proposal not found")
    if proposal.status != FinanceProposalStatus.PENDING:
        raise ValueError("Only pending proposals can be approved")

    old_snapshot = _proposal_dict(proposal)
    client_result: dict[str, Any] | None = None
    payout_result: dict[str, Any] | None = None
    record_result: dict[str, Any] | None = None

    if proposal.proposal_type == FinanceCorrectionProposalType.PAYOUT_ONLY_EDIT:
        if proposal.new_payout_amount_inr is None:
            raise ValueError("Missing new payout amount")
        payout_result = _apply_payout_correction(
            db,
            case_id=proposal.case_id,
            billing_month=proposal.billing_month,
            new_payout_inr=float(proposal.new_payout_amount_inr),
            reason=proposal.reason,
            user_id=user_id,
        )
    elif proposal.wrong_side == FinanceWrongSide.RECORD_WRONG:
        record_result = _apply_record_correction(
            db,
            case_id=proposal.case_id,
            billing_month=proposal.billing_month,
            payload=proposal.record_correction_payload,
            reason=proposal.reason,
            user_id=user_id,
        )
    else:
        if proposal.new_client_amount_inr is not None and proposal.client_invoice_id:
            inv = db.get(ClientInvoice, proposal.client_invoice_id)
            if inv:
                client_result = _apply_client_correction(
                    db,
                    inv=inv,
                    new_total_inr=float(proposal.new_client_amount_inr),
                    reason=proposal.reason,
                    user_id=user_id,
                )
        if proposal.new_payout_amount_inr is not None:
            payout_result = _apply_payout_correction(
                db,
                case_id=proposal.case_id,
                billing_month=proposal.billing_month,
                new_payout_inr=float(proposal.new_payout_amount_inr),
                reason=proposal.reason,
                user_id=user_id,
            )

    proposal.status = FinanceProposalStatus.APPROVED
    proposal.reviewed_by_user_id = user_id
    proposal.reviewed_at = _now()
    db.flush()

    audit_payload = {
        "proposalId": proposal.id,
        "clientResult": client_result,
        "payoutResult": payout_result,
        "recordResult": record_result,
        "reason": proposal.reason,
    }
    log_audit(
        db,
        actor_user_id=user_id,
        action="finance_correction_approved",
        entity_type="finance_correction_proposal",
        entity_id=proposal.id,
        old_value=old_snapshot,
        new_value=audit_payload,
        case_id=proposal.case_id,
    )
    if client_result and proposal.client_invoice_id:
        log_audit(
            db,
            actor_user_id=user_id,
            action="client_invoice_finance_correction",
            entity_type="client_invoice",
            entity_id=proposal.client_invoice_id,
            new_value={**client_result, "reason": proposal.reason},
            case_id=proposal.case_id,
        )
    if payout_result:
        log_audit(
            db,
            actor_user_id=user_id,
            action="therapist_payout_finance_correction",
            entity_type="invoice",
            entity_id=proposal.therapist_invoice_id,
            new_value={**payout_result, "reason": proposal.reason},
            case_id=proposal.case_id,
        )

    return {
        "proposal": _proposal_dict(proposal),
        "clientResult": client_result,
        "payoutResult": payout_result,
        "recordResult": record_result,
    }


def reject_proposal(db: Session, *, proposal_id: int, user_id: int) -> dict[str, Any]:
    proposal = db.get(FinanceCorrectionProposal, proposal_id)
    if not proposal:
        raise ValueError("Proposal not found")
    if proposal.status != FinanceProposalStatus.PENDING:
        raise ValueError("Only pending proposals can be rejected")
    old_snapshot = _proposal_dict(proposal)
    proposal.status = FinanceProposalStatus.REJECTED
    proposal.reviewed_by_user_id = user_id
    proposal.reviewed_at = _now()
    db.flush()
    log_audit(
        db,
        actor_user_id=user_id,
        action="finance_correction_rejected",
        entity_type="finance_correction_proposal",
        entity_id=proposal.id,
        old_value=old_snapshot,
        new_value={"status": "REJECTED"},
        case_id=proposal.case_id,
    )
    return _proposal_dict(proposal)


def get_proposal(db: Session, proposal_id: int) -> dict[str, Any] | None:
    p = db.get(FinanceCorrectionProposal, proposal_id)
    return _proposal_dict(p) if p else None


def list_proposals(
    db: Session,
    *,
    case_id: Optional[int] = None,
    billing_month: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    stmt = select(FinanceCorrectionProposal).order_by(FinanceCorrectionProposal.id.desc())
    if case_id:
        stmt = stmt.where(FinanceCorrectionProposal.case_id == case_id)
    if billing_month:
        ym = billing_composer_service.normalize_billing_month(billing_month)
        stmt = stmt.where(FinanceCorrectionProposal.billing_month == ym)
    if status:
        stmt = stmt.where(FinanceCorrectionProposal.status == FinanceProposalStatus(status.upper()))
    rows = db.scalars(stmt.limit(max(1, min(limit, 200)))).all()
    return [_proposal_dict(r) for r in rows]
