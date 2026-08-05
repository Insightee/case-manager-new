"""Canonical therapist payout settlement — gross → TDS → deductions → net."""
from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.invoice import Invoice, InvoiceStatus
from app.models.invoice_line import InvoiceCaseLine
from app.models.therapist_profile import TherapistProfile
from app.models.therapist_statement_dispute import TherapistStatementDispute
from app.services import finance_payout_deduction_service

_OPEN_DISPUTE_STATUSES = {"OPEN", "UNDER_REVIEW"}


def resolve_tds_rate_percent(db: Session, *, therapist_user_id: int) -> float:
    profile = db.scalar(select(TherapistProfile).where(TherapistProfile.user_id == therapist_user_id))
    if profile and profile.tds_rate_percent is not None:
        return float(profile.tds_rate_percent)
    return float(getattr(settings, "finance_default_tds_rate_percent", 10.0))


def _invoice_gross_inr(db: Session, invoice: Invoice) -> float:
    lines = db.scalars(select(InvoiceCaseLine).where(InvoiceCaseLine.invoice_id == invoice.id)).all()
    if lines:
        return round(sum(float(cl.therapist_share_inr or 0) for cl in lines), 2)
    return round(float(invoice.subtotal_inr or invoice.amount_inr or 0), 2)


def _invoice_deductions(db: Session, invoice: Invoice) -> list[dict[str, Any]]:
    case_lines = db.scalars(select(InvoiceCaseLine).where(InvoiceCaseLine.invoice_id == invoice.id)).all()
    out: list[dict[str, Any]] = []
    seen: set[int] = set()
    for cl in case_lines:
        if cl.case_id in seen:
            continue
        seen.add(cl.case_id)
        out.extend(
            finance_payout_deduction_service.list_deductions(
                db, case_id=cl.case_id, billing_month=invoice.month, include_reversed=False
            )
        )
    return out


def _has_open_statement_dispute(db: Session, invoice: Invoice) -> bool:
    rows = db.scalars(
        select(TherapistStatementDispute).where(
            TherapistStatementDispute.invoice_id == invoice.id,
            TherapistStatementDispute.status.in_(_OPEN_DISPUTE_STATUSES),
        )
    ).all()
    return bool(rows)


def compute_invoice_settlement(db: Session, invoice: Invoice) -> dict[str, Any]:
    """Settlement ladder for a therapist invoice — single composed net source."""
    gross = _invoice_gross_inr(db, invoice)
    tds_rate = resolve_tds_rate_percent(db, therapist_user_id=invoice.therapist_user_id)
    deductions = _invoice_deductions(db, invoice)
    ladder = finance_payout_deduction_service.compute_payout_ladder(
        gross_inr=gross,
        tds_rate_percent=tds_rate,
        deductions=deductions,
    )
    blocked = bool(ladder.get("blocked"))
    block_reason = ladder.get("blockReason")
    if invoice.status != InvoiceStatus.APPROVED:
        blocked = True
        block_reason = block_reason or "Statement must be APPROVED before export"
    if _has_open_statement_dispute(db, invoice):
        blocked = True
        block_reason = block_reason or "Open therapist statement dispute — resolve before export"
    return {
        "invoiceId": invoice.id,
        "therapistUserId": invoice.therapist_user_id,
        "month": invoice.month,
        "status": invoice.status.value,
        "grossInr": ladder["grossInr"],
        "tdsRatePercent": ladder["tdsRatePercent"],
        "tdsInr": ladder["tdsInr"],
        "afterTdsInr": ladder["afterTdsInr"],
        "deductionsInr": ladder["deductionsInr"],
        "additionsInr": ladder.get("additionsInr", 0),
        "netInr": ladder["netInr"],
        "blocked": blocked,
        "blockedReason": block_reason,
        "deductions": deductions,
    }


def settlement_preview(db: Session, *, invoice_id: int) -> dict[str, Any]:
    invoice = db.get(Invoice, invoice_id)
    if not invoice:
        raise ValueError("Invoice not found")
    return compute_invoice_settlement(db, invoice)


def assert_exportable(db: Session, invoice: Invoice) -> dict[str, Any]:
    settlement = compute_invoice_settlement(db, invoice)
    if settlement["blocked"]:
        raise ValueError(settlement.get("blockedReason") or "Payout blocked — needs review")
    if settlement["netInr"] < 0:
        raise ValueError("Net payout cannot be negative")
    return settlement


def snapshot_settlement_on_invoice(db: Session, invoice: Invoice, settlement: dict[str, Any]) -> None:
    invoice.tds_inr = settlement["tdsInr"]
    invoice.net_payable_inr = settlement["netInr"]
    db.flush()
