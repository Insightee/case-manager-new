from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.invoice import Invoice
from app.models.therapist_payout_flag import TherapistPayoutFlag


def billing_month_key(value: str | date) -> str:
    if isinstance(value, date):
        return value.strftime("%Y-%m")
    raw = (value or "").strip()
    for pattern in ("%Y-%m", "%b %Y", "%B %Y"):
        try:
            return datetime.strptime(raw, pattern).strftime("%Y-%m")
        except ValueError:
            continue
    return raw


def create_reassignment_flag(
    db: Session,
    *,
    therapist_user_id: int,
    effective_date: date,
    case_id: int,
    outgoing_assignment_id: int,
    flagged_by_user_id: int,
    reason: str | None,
) -> TherapistPayoutFlag:
    flag = TherapistPayoutFlag(
        therapist_user_id=therapist_user_id,
        billing_month=billing_month_key(effective_date),
        case_id=case_id,
        outgoing_assignment_id=outgoing_assignment_id,
        flagged_by_user_id=flagged_by_user_id,
        reason=(reason or "").strip() or None,
        is_active=True,
    )
    db.add(flag)
    db.flush()
    return flag


def active_flagged_keys(
    db: Session, invoices: Iterable[Invoice]
) -> set[tuple[int, str]]:
    invoice_rows = list(invoices)
    therapist_ids = {row.therapist_user_id for row in invoice_rows}
    if not therapist_ids:
        return set()
    month_keys = {billing_month_key(row.month) for row in invoice_rows}
    rows = db.execute(
        select(
            TherapistPayoutFlag.therapist_user_id,
            TherapistPayoutFlag.billing_month,
        ).where(
            TherapistPayoutFlag.therapist_user_id.in_(therapist_ids),
            TherapistPayoutFlag.billing_month.in_(month_keys),
            TherapistPayoutFlag.is_active.is_(True),
        )
    ).all()
    return {(int(therapist_id), month) for therapist_id, month in rows}


def is_invoice_flagged(
    invoice: Invoice, flagged_keys: set[tuple[int, str]]
) -> bool:
    return (
        invoice.therapist_user_id,
        billing_month_key(invoice.month),
    ) in flagged_keys


def clear_flags_for_paid_invoice(db: Session, invoice: Invoice) -> int:
    month = billing_month_key(invoice.month)
    rows = list(
        db.scalars(
            select(TherapistPayoutFlag).where(
                TherapistPayoutFlag.therapist_user_id
                == invoice.therapist_user_id,
                TherapistPayoutFlag.billing_month == month,
                TherapistPayoutFlag.is_active.is_(True),
            )
        ).all()
    )
    cleared_at = datetime.now(timezone.utc)
    for row in rows:
        row.is_active = False
        row.cleared_at = cleared_at
        row.cleared_invoice_id = invoice.id
    if rows:
        db.flush()
    return len(rows)
