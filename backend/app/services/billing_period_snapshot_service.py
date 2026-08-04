"""Month-close billing snapshots — frozen payout reports and per-case period records."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.billing_validation import case_billing_dict
from app.models.billing_period_snapshot import BillingMonthClose, BillingMonthCloseStatus, CaseBillingPeriodSnapshot
from app.models.case import Case
from app.models.client_billing import ClientInvoice
from app.models.ledger_billing import BillableStatus, BillingLedger
from app.services import billing_composer_service, finance_payout_preview_service
from app.services.billing_ledger_service import reconcile_month


def normalize_billing_month(value: str | None) -> str:
    return billing_composer_service.normalize_billing_month(value or "")


def get_month_close(db: Session, billing_month: str) -> BillingMonthClose | None:
    ym = normalize_billing_month(billing_month)
    return db.scalars(
        select(BillingMonthClose).where(BillingMonthClose.billing_month == ym).limit(1)
    ).first()


def is_billing_month_closed(db: Session, billing_month: str) -> bool:
    row = get_month_close(db, billing_month)
    return row is not None and row.status == BillingMonthCloseStatus.CLOSED


def get_closed_payout_preview_rows(db: Session, billing_month: str) -> list[dict] | None:
    row = get_month_close(db, billing_month)
    if not row or row.status != BillingMonthCloseStatus.CLOSED:
        return None
    return list(row.payout_preview_rows or [])


def get_case_period_snapshot(
    db: Session, *, case_id: int, billing_month: str
) -> CaseBillingPeriodSnapshot | None:
    ym = normalize_billing_month(billing_month)
    return db.scalars(
        select(CaseBillingPeriodSnapshot).where(
            CaseBillingPeriodSnapshot.case_id == case_id,
            CaseBillingPeriodSnapshot.billing_month == ym,
        )
    ).first()


def margin_rows_from_case_snapshots(db: Session, billing_month: str) -> list[dict] | None:
    if not is_billing_month_closed(db, billing_month):
        return None
    ym = normalize_billing_month(billing_month)
    rows = db.scalars(
        select(CaseBillingPeriodSnapshot)
        .where(CaseBillingPeriodSnapshot.billing_month == ym)
        .order_by(CaseBillingPeriodSnapshot.case_id)
    ).all()
    return [
        {
            "caseId": r.case_id,
            "clientTotalInr": float(r.ledger_total_inr or 0),
            "therapistTotalInr": float(r.therapist_payout_total_inr or 0),
            "marginInr": float(r.margin_inr or 0),
            "sessionCount": int(r.session_count or 0),
        }
        for r in rows
    ]


def _ledger_totals_for_case(db: Session, case_id: int, billing_month: str) -> dict:
    ym = normalize_billing_month(billing_month)
    ledger_rows = db.scalars(
        select(BillingLedger).where(
            BillingLedger.case_id == case_id,
            BillingLedger.ledger_month == ym,
            BillingLedger.billable_status.in_([BillableStatus.BILLABLE, BillableStatus.INVOICED]),
        )
    ).all()
    subtotal = sum(float(r.amount_inr or 0) for r in ledger_rows)
    tax = sum(float(r.gst_amount_inr or 0) for r in ledger_rows)
    total = sum(float(r.total_inr or 0) for r in ledger_rows)
    return {"subtotal": round(subtotal, 2), "tax": round(tax, 2), "total": round(total, 2)}


def upsert_case_period_snapshot(
    db: Session,
    *,
    case_id: int,
    billing_month: str,
    actor_user_id: int | None = None,
    client_invoice_id: int | None = None,
) -> CaseBillingPeriodSnapshot:
    ym = normalize_billing_month(billing_month)
    case = db.get(Case, case_id)
    if not case:
        raise ValueError("Case not found")

    totals = _ledger_totals_for_case(db, case_id, ym)
    reconcile = reconcile_month(db, case_id=case_id, billing_month=ym)

    if client_invoice_id is None:
        inv = db.scalars(
            select(ClientInvoice)
            .where(ClientInvoice.case_id == case_id, ClientInvoice.billing_month == ym)
            .order_by(ClientInvoice.id.desc())
            .limit(1)
        ).first()
        client_invoice_id = inv.id if inv else None

    existing = get_case_period_snapshot(db, case_id=case_id, billing_month=ym)
    now = datetime.now(timezone.utc)
    payload = {
        "billing_snapshot": case_billing_dict(case),
        "client_invoice_id": client_invoice_id,
        "ledger_subtotal_inr": totals["subtotal"],
        "ledger_tax_inr": totals["tax"],
        "ledger_total_inr": totals["total"],
        "margin_inr": reconcile.get("marginInr"),
        "therapist_payout_total_inr": reconcile.get("therapistPayoutTotalInr"),
        "session_count": reconcile.get("sessionCount"),
        "closed_at": now,
        "closed_by_user_id": actor_user_id,
    }
    if existing:
        for key, value in payload.items():
            setattr(existing, key, value)
        db.flush()
        return existing

    row = CaseBillingPeriodSnapshot(case_id=case_id, billing_month=ym, **payload)
    db.add(row)
    db.flush()
    return row


def close_billing_month(
    db: Session,
    *,
    billing_month: str,
    actor_user_id: int,
    notes: str | None = None,
    force: bool = False,
) -> dict:
    """Capture payout preview + per-case snapshots for a billing month."""
    ym = normalize_billing_month(billing_month)
    existing = get_month_close(db, ym)
    if existing and not force:
        raise ValueError(f"Billing month {ym} is already closed")

    payout_rows = finance_payout_preview_service.payout_preview_rows(db, ym)

    case_ids: set[int] = set()
    for row in payout_rows:
        cid = row.get("caseId")
        if cid is not None:
            case_ids.add(int(cid))

    ledger_case_ids = db.scalars(
        select(BillingLedger.case_id.distinct()).where(BillingLedger.ledger_month == ym)
    ).all()
    case_ids.update(ledger_case_ids)

    for case_id in sorted(case_ids):
        upsert_case_period_snapshot(
            db,
            case_id=case_id,
            billing_month=ym,
            actor_user_id=actor_user_id,
        )

    now = datetime.now(timezone.utc)
    if existing:
        existing.payout_preview_rows = payout_rows
        existing.closed_at = now
        existing.closed_by_user_id = actor_user_id
        existing.notes = notes
        existing.status = BillingMonthCloseStatus.CLOSED
        close_row = existing
    else:
        close_row = BillingMonthClose(
            billing_month=ym,
            status=BillingMonthCloseStatus.CLOSED,
            payout_preview_rows=payout_rows,
            closed_at=now,
            closed_by_user_id=actor_user_id,
            notes=notes,
        )
        db.add(close_row)

    db.flush()
    return {
        "billingMonth": ym,
        "status": close_row.status.value,
        "payoutRowCount": len(payout_rows),
        "caseSnapshotCount": len(case_ids),
        "closedAt": close_row.closed_at.isoformat() if close_row.closed_at else None,
    }


def month_close_dict(row: BillingMonthClose) -> dict:
    return {
        "billingMonth": row.billing_month,
        "status": row.status.value,
        "payoutRowCount": len(row.payout_preview_rows or []),
        "closedAt": row.closed_at.isoformat() if row.closed_at else None,
        "closedByUserId": row.closed_by_user_id,
        "notes": row.notes,
    }
