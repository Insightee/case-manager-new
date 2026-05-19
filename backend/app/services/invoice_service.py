from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.invoice import Invoice, InvoiceStatus
from app.models.review import Review, ReviewDecision


def list_invoices(db: Session, status: InvoiceStatus | None = None) -> list[Invoice]:
    stmt = select(Invoice).order_by(Invoice.created_at.desc())
    if status:
        stmt = stmt.where(Invoice.status == status)
    return list(db.scalars(stmt).all())


def review_invoice(
    db: Session,
    invoice: Invoice,
    reviewer_user_id: int,
    decision: ReviewDecision,
    comment: str | None,
) -> Invoice:
    review = Review(
        entity_type="invoice",
        entity_id=invoice.id,
        reviewer_user_id=reviewer_user_id,
        decision=decision,
        comment=comment,
    )
    db.add(review)
    if decision == ReviewDecision.APPROVE:
        invoice.status = InvoiceStatus.APPROVED
    else:
        invoice.status = InvoiceStatus.REJECTED
        invoice.reviewer_comment = comment
    db.flush()
    return invoice
