"""Raise therapist payout invoices that are still unsubmitted at month close."""

from __future__ import annotations

from calendar import monthrange
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.audit import log_audit
from app.core.timezone import IST
from app.models.assignment import CaseAssignment
from app.models.invoice import Invoice
from app.services.invoice_billing_service import (
    build_month_preview,
    parse_month,
    submit_invoice_from_preview,
)

AUTO_SUBMIT_NOTE = (
    "Auto-submitted at month close. This payout had not been submitted by the last day of the month."
)


def billing_month_due_at_close(now: datetime) -> str | None:
    """YYYY-MM when `now` is 23:59 or later on the last calendar day in Asia/Kolkata."""
    local = now.astimezone(IST) if now.tzinfo else now.replace(tzinfo=IST)
    last_day = monthrange(local.year, local.month)[1]
    if local.day != last_day or (local.hour, local.minute) < (23, 59):
        return None
    return f"{local.year}-{local.month:02d}"


def _therapist_ids_overlapping_month(db: Session, year: int, month_num: int) -> list[int]:
    start = datetime(year, month_num, 1, tzinfo=ZoneInfo("UTC")).date()
    end = datetime(year, month_num, monthrange(year, month_num)[1], tzinfo=ZoneInfo("UTC")).date()
    rows = db.scalars(
        select(CaseAssignment.therapist_user_id)
        .where(
            CaseAssignment.start_date <= end,
            or_(CaseAssignment.end_date.is_(None), CaseAssignment.end_date >= start),
        )
        .distinct()
    ).all()
    return sorted({int(row) for row in rows})


def auto_submit_unsubmitted_invoices(db: Session, month: str) -> dict:
    """Submit one invoice per therapist who has no invoice for the month and a billable preview.

    Each therapist is committed on its own. A package with no session count, or a preview
    with no payout, is recorded and left unsubmitted.
    """
    year, month_num, label = parse_month(month)
    ym = f"{year}-{month_num:02d}"
    submitted: list[dict] = []
    skipped: list[dict] = []

    for therapist_user_id in _therapist_ids_overlapping_month(db, year, month_num):
        existing = db.scalars(
            select(Invoice.id).where(
                Invoice.therapist_user_id == therapist_user_id,
                Invoice.month.in_([label, ym]),
            )
        ).first()
        if existing:
            skipped.append(
                {
                    "therapist_user_id": therapist_user_id,
                    "reason": "already_submitted",
                    "invoice_id": int(existing),
                }
            )
            continue
        try:
            preview = build_month_preview(db, therapist_user_id, ym)
            invoice = submit_invoice_from_preview(db, therapist_user_id, preview, AUTO_SUBMIT_NOTE)
            log_audit(
                db,
                actor_user_id=None,
                action="auto_submit",
                entity_type="invoice",
                entity_id=invoice.id,
                new_value={
                    "therapist_user_id": therapist_user_id,
                    "month": label,
                    "amount_inr": float(invoice.amount_inr or 0),
                },
                user_agent="month-end-auto-submit",
            )
            db.commit()
            submitted.append(
                {
                    "therapist_user_id": therapist_user_id,
                    "invoice_id": invoice.id,
                    "amount_inr": float(invoice.amount_inr or 0),
                }
            )
        except Exception as exc:
            db.rollback()
            skipped.append(
                {
                    "therapist_user_id": therapist_user_id,
                    "reason": str(exc)[:180],
                }
            )

    return {"month": ym, "submitted": submitted, "skipped": skipped}
