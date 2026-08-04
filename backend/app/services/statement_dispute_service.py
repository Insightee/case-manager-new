"""Therapist statement disputes — dispute-tracking, not billing math.

Standalone service over the additive ``therapist_statement_disputes`` table.
It never edits an amount and never touches the payout engine
(invoice_billing_service / ledger). On a submitted invoice it reuses the
existing ``InvoiceStatus.QUERIED`` flip — no parallel status concept.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.invoice import Invoice, InvoiceStatus
from app.models.therapist_statement_dispute import TherapistStatementDispute

# A dispute makes a submitted statement "queried" for finance to look at.
_FLIP_TO_QUERIED_FROM = {InvoiceStatus.IN_REVIEW, InvoiceStatus.APPROVED}


def create_statement_dispute(
    db: Session,
    *,
    therapist_user_id: int,
    month: str,
    comment: str,
    session_ids: list[int] | None = None,
    invoice_id: int | None = None,
    reason_code: str | None = None,
) -> TherapistStatementDispute:
    comment = (comment or "").strip()
    if not comment:
        raise ValueError("A comment is required to raise a dispute")

    invoice = None
    if invoice_id is not None:
        invoice = db.get(Invoice, invoice_id)
        if not invoice or invoice.therapist_user_id != therapist_user_id:
            raise ValueError("Invoice not found")

    # De-duplicate while preserving order; coerce to plain ints.
    marked = list(dict.fromkeys(int(s) for s in (session_ids or [])))

    dispute = TherapistStatementDispute(
        therapist_user_id=therapist_user_id,
        month=month,
        invoice_id=invoice_id,
        status="OPEN",
        reason_code=reason_code,
        comment=comment,
        disputed_session_ids=marked,
    )
    db.add(dispute)

    # Reuse the existing invoice status — no amount is ever changed here.
    if invoice is not None and invoice.status in _FLIP_TO_QUERIED_FROM:
        invoice.status = InvoiceStatus.QUERIED

    db.flush()
    return dispute


def list_statement_disputes(
    db: Session,
    *,
    therapist_user_id: int | None = None,
    month: str | None = None,
) -> list[TherapistStatementDispute]:
    q = db.query(TherapistStatementDispute)
    if therapist_user_id is not None:
        q = q.filter(TherapistStatementDispute.therapist_user_id == therapist_user_id)
    if month:
        q = q.filter(TherapistStatementDispute.month == month)
    return q.order_by(TherapistStatementDispute.created_at.desc()).all()


def dispute_dict(d: TherapistStatementDispute) -> dict:
    return {
        "id": d.id,
        "therapist_user_id": d.therapist_user_id,
        "month": d.month,
        "invoice_id": d.invoice_id,
        "status": d.status,
        "reason_code": d.reason_code,
        "comment": d.comment,
        "disputed_session_ids": d.disputed_session_ids or [],
        "created_at": d.created_at.isoformat() if d.created_at else None,
    }
