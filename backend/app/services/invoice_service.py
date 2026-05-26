from __future__ import annotations

from datetime import date as date_type, datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.invoice import Invoice, InvoiceStatus
from app.models.review import Review, ReviewDecision
from app.models.user import User


def list_invoices(
    db: Session,
    status: InvoiceStatus | None = None,
    *,
    year: Optional[int] = None,
    month: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    search: Optional[str] = None,
) -> list[Invoice]:
    stmt = select(Invoice).order_by(Invoice.created_at.desc())
    if status:
        stmt = stmt.where(Invoice.status == status)
    if year:
        stmt = stmt.where(Invoice.month.contains(str(year)))
    if month:
        stmt = stmt.where(Invoice.month == month)
    if date_from:
        start = datetime.combine(date_type.fromisoformat(date_from), datetime.min.time()).replace(tzinfo=timezone.utc)
        stmt = stmt.where(Invoice.created_at >= start)
    if date_to:
        end_day = date_type.fromisoformat(date_to) + timedelta(days=1)
        end = datetime.combine(end_day, datetime.min.time()).replace(tzinfo=timezone.utc)
        stmt = stmt.where(Invoice.created_at < end)
    rows = list(db.scalars(stmt).all())
    if not search:
        return rows
    q = search.strip().lower()
    if not q:
        return rows
    therapist_ids = {i.therapist_user_id for i in rows}
    names = {}
    if therapist_ids:
        for u in db.scalars(select(User).where(User.id.in_(therapist_ids))).all():
            names[u.id] = (u.full_name or "").lower()
    return [
        i
        for i in rows
        if q in (names.get(i.therapist_user_id) or "")
        or q in (i.month or "").lower()
        or q in str(i.therapist_user_id)
    ]


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
