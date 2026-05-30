"""Bulk finance actions with per-item error isolation."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.invoice import Invoice, InvoiceStatus
from app.models.review import ReviewDecision
from app.services import client_invoice_draft_service, invoice_service


def bulk_client_invoices(
    db: Session,
    *,
    action: str,
    case_ids: list[int],
    billing_month: str,
    admin_user_id: int,
    include_pending: bool = False,
) -> dict:
    succeeded = []
    failed = []
    for case_id in case_ids:
        try:
            if action == "build_from_ledger":
                result = client_invoice_draft_service.generate_draft_from_ledger(
                    db,
                    case_id=case_id,
                    billing_month=billing_month,
                    actor_user_id=admin_user_id,
                    include_pending=include_pending,
                )
                succeeded.append({"caseId": case_id, "invoiceId": result["id"]})
            else:
                raise ValueError(f"Unsupported action: {action}")
        except Exception as e:
            failed.append({"caseId": case_id, "error": str(e)})
    if succeeded:
        db.flush()
    return {"succeeded": succeeded, "failed": failed}


def bulk_therapist_payouts(
    db: Session,
    *,
    action: str,
    invoice_ids: list[int],
    reviewer_user_id: int,
    paid_amount_by_id: dict[int, float] | None = None,
) -> dict:
    succeeded = []
    failed = []
    for invoice_id in invoice_ids:
        try:
            inv = db.get(Invoice, invoice_id)
            if not inv:
                raise ValueError("Invoice not found")
            if action == "approve":
                invoice_service.review_invoice(
                    db, inv, reviewer_user_id, ReviewDecision.APPROVE, None
                )
                succeeded.append({"invoiceId": invoice_id})
            elif action == "mark_paid":
                if inv.status != InvoiceStatus.APPROVED:
                    raise ValueError("Only approved invoices can be marked paid")
                amt = (paid_amount_by_id or {}).get(invoice_id)
                inv.paid_amount_inr = amt if amt is not None else inv.amount_inr
                inv.status = InvoiceStatus.PAID
                succeeded.append({"invoiceId": invoice_id})
            else:
                raise ValueError(f"Unsupported action: {action}")
        except Exception as e:
            failed.append({"invoiceId": invoice_id, "error": str(e)})
    return {"succeeded": succeeded, "failed": failed}
