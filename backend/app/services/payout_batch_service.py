"""Therapist payout batch export, idempotency, and status sync."""
from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.audit import log_audit
from app.core.feature_flags import payout_release_enabled
from app.models.external_ref import ExternalProvider
from app.models.invoice import Invoice, InvoiceStatus
from app.models.therapist_payout_settlement import (
    TherapistPayoutBatch,
    TherapistPayoutBatchStatus,
    TherapistPayoutTransfer,
    TherapistPayoutTransferStatus,
)
from app.services import external_ref_service, payout_settlement_service
from app.services.payout_provider import PayoutTransferRequest, get_payout_provider

_PROVIDER = ExternalProvider.RAZORPAY_PAYOUT.value
_ACTIVE_TRANSFER_STATUSES = frozenset(
    {
        TherapistPayoutTransferStatus.PENDING.value,
        TherapistPayoutTransferStatus.PROCESSING.value,
        TherapistPayoutTransferStatus.PAID.value,
    }
)


class IdempotencyMismatchError(ValueError):
    """Raised when an idempotency key is reused with a different invoice set."""


class InvoiceExportLockedError(ValueError):
    """Raised when an invoice already has an active payout transfer."""


def _batch_dict(batch: TherapistPayoutBatch, transfers: list[TherapistPayoutTransfer] | None = None) -> dict[str, Any]:
    xfer_rows = transfers or list(batch.transfers or [])
    return {
        "id": batch.id,
        "billingMonth": batch.billing_month,
        "status": batch.status,
        "provider": batch.provider,
        "idempotencyKey": batch.idempotency_key,
        "providerBatchRef": batch.provider_batch_ref,
        "createdByUserId": batch.created_by_user_id,
        "transferCount": len(xfer_rows),
        "transfers": [_transfer_dict(t) for t in xfer_rows],
    }


def _transfer_dict(t: TherapistPayoutTransfer) -> dict[str, Any]:
    return {
        "id": t.id,
        "batchId": t.batch_id,
        "invoiceId": t.invoice_id,
        "grossInr": float(t.gross_inr),
        "tdsRatePercent": float(t.tds_rate_percent),
        "tdsInr": float(t.tds_inr),
        "deductionsInr": float(t.deductions_inr),
        "netInr": float(t.net_inr),
        "providerRef": t.provider_ref,
        "status": t.status,
        "failureReason": t.failure_reason,
    }


def get_batch_by_idempotency(db: Session, idempotency_key: str) -> TherapistPayoutBatch | None:
    return db.scalar(select(TherapistPayoutBatch).where(TherapistPayoutBatch.idempotency_key == idempotency_key))


def _active_transfer_for_invoice(db: Session, invoice_id: int) -> TherapistPayoutTransfer | None:
    return db.scalar(
        select(TherapistPayoutTransfer)
        .where(
            TherapistPayoutTransfer.invoice_id == invoice_id,
            TherapistPayoutTransfer.status.in_(_ACTIVE_TRANSFER_STATUSES),
        )
        .order_by(TherapistPayoutTransfer.id.desc())
        .limit(1)
    )


def _assert_invoice_exportable(db: Session, inv: Invoice) -> dict[str, Any]:
    if inv.status not in (InvoiceStatus.APPROVED,):
        raise ValueError(f"Invoice {inv.id} must be APPROVED before export")
    active = _active_transfer_for_invoice(db, inv.id)
    if active is not None:
        raise InvoiceExportLockedError(
            f"Invoice {inv.id} already has an active payout transfer (batch {active.batch_id})"
        )
    return payout_settlement_service.assert_exportable(db, inv)


def _invoice_ids_for_batch(db: Session, batch_id: int) -> list[int]:
    rows = db.scalars(
        select(TherapistPayoutTransfer.invoice_id).where(TherapistPayoutTransfer.batch_id == batch_id)
    ).all()
    return sorted(int(i) for i in rows)


def reserve_export_batch(
    db: Session,
    *,
    invoice_ids: list[int],
    idempotency_key: str,
    created_by_user_id: int,
    billing_month: str | None = None,
) -> dict[str, Any]:
    """Outbox phase 1 — persist EXPORTING batch + transfers before provider call."""
    key = (idempotency_key or "").strip()
    if not key:
        raise ValueError("Idempotency key is required")
    if not invoice_ids:
        raise ValueError("Select at least one approved statement")

    requested_ids = sorted(set(invoice_ids))
    existing = get_batch_by_idempotency(db, key)
    if existing:
        stored_ids = _invoice_ids_for_batch(db, existing.id)
        if stored_ids != requested_ids:
            raise IdempotencyMismatchError(
                "Idempotency key reused with a different invoice set — cannot replay with mismatched invoices"
            )
        transfers = list(
            db.scalars(select(TherapistPayoutTransfer).where(TherapistPayoutTransfer.batch_id == existing.id)).all()
        )
        return {"alreadyExported": True, "batch": _batch_dict(existing, transfers)}

    invoices: list[Invoice] = []
    settlements: list[dict[str, Any]] = []
    for iid in requested_ids:
        inv = db.get(Invoice, iid)
        if not inv:
            raise ValueError(f"Invoice {iid} not found")
        settlement = _assert_invoice_exportable(db, inv)
        invoices.append(inv)
        settlements.append(settlement)

    month = billing_month or (invoices[0].month if invoices else "")
    batch = TherapistPayoutBatch(
        billing_month=month,
        status=TherapistPayoutBatchStatus.EXPORTING.value,
        provider="MOCK",
        idempotency_key=key,
        created_by_user_id=created_by_user_id,
    )
    db.add(batch)
    db.flush()

    transfer_rows: list[TherapistPayoutTransfer] = []
    for inv, sett in zip(invoices, settlements):
        inv.status = InvoiceStatus.EXPORTING
        xfer = TherapistPayoutTransfer(
            batch_id=batch.id,
            invoice_id=inv.id,
            gross_inr=sett["grossInr"],
            tds_rate_percent=sett["tdsRatePercent"],
            tds_inr=sett["tdsInr"],
            deductions_inr=sett["deductionsInr"],
            net_inr=sett["netInr"],
            status=TherapistPayoutTransferStatus.PENDING.value,
        )
        db.add(xfer)
        transfer_rows.append(xfer)
        payout_settlement_service.snapshot_settlement_on_invoice(db, inv, sett)
    db.flush()

    log_audit(
        db,
        actor_user_id=created_by_user_id,
        action="therapist_payout_batch_reserved",
        entity_type="therapist_payout_batch",
        entity_id=batch.id,
        new_value={"invoiceIds": requested_ids, "idempotencyKey": key},
    )
    db.flush()
    return {"alreadyExported": False, "batch": _batch_dict(batch, transfer_rows)}


def dispatch_export_batch(
    db: Session,
    *,
    batch_id: int,
    actor_user_id: int | None = None,
) -> dict[str, Any]:
    """Outbox phase 2 — call provider after reserved rows are committed."""
    batch = db.get(TherapistPayoutBatch, batch_id)
    if not batch:
        raise ValueError("Batch not found")
    if batch.status != TherapistPayoutBatchStatus.EXPORTING.value:
        transfers = list(
            db.scalars(select(TherapistPayoutTransfer).where(TherapistPayoutTransfer.batch_id == batch.id)).all()
        )
        return {"alreadyExported": True, "batch": _batch_dict(batch, transfers)}

    transfers = list(
        db.scalars(select(TherapistPayoutTransfer).where(TherapistPayoutTransfer.batch_id == batch.id)).all()
    )
    if not transfers:
        raise ValueError("Batch has no transfers")

    provider = get_payout_provider()
    xfer_requests: list[PayoutTransferRequest] = []
    for t in transfers:
        inv = db.get(Invoice, t.invoice_id)
        xfer_requests.append(
            PayoutTransferRequest(
                invoice_id=t.invoice_id,
                amount_inr=float(t.net_inr),
                reference=f"PAYOUT-{t.invoice_id}",
                therapist_user_id=inv.therapist_user_id if inv else 0,
            )
        )
    result = provider.create_batch(transfers=xfer_requests, idempotency_key=batch.idempotency_key)

    batch.provider = result.provider
    batch.provider_batch_ref = result.batch_ref
    batch.status = TherapistPayoutBatchStatus.EXPORTED.value

    provider_by_invoice = {t["invoiceId"]: t for t in result.transfers}
    failed_count = 0
    for xfer in transfers:
        prov = provider_by_invoice.get(xfer.invoice_id, {})
        if prov.get("status") == "failed":
            xfer.status = TherapistPayoutTransferStatus.FAILED.value
            xfer.failure_reason = prov.get("message") or "Provider reported failure"
            xfer.provider_ref = prov.get("providerRef")
            _return_invoice_to_queue(db, xfer.invoice_id)
            failed_count += 1
        else:
            xfer.status = TherapistPayoutTransferStatus.PROCESSING.value
            xfer.provider_ref = prov.get("providerRef")
        db.flush()

    if failed_count == len(transfers):
        batch.status = TherapistPayoutBatchStatus.FAILED.value
    elif failed_count:
        batch.status = TherapistPayoutBatchStatus.PARTIAL_FAILED.value

    external_ref_service.upsert_external_ref(
        db, _PROVIDER, "therapist_payout_batch", batch.id, result.batch_ref or f"BATCH-{batch.id}"
    )
    for xfer in transfers:
        if xfer.provider_ref:
            external_ref_service.upsert_external_ref(
                db, _PROVIDER, "therapist_payout_transfer", xfer.id, xfer.provider_ref
            )

    if actor_user_id:
        log_audit(
            db,
            actor_user_id=actor_user_id,
            action="therapist_payout_batch_exported",
            entity_type="therapist_payout_batch",
            entity_id=batch.id,
            new_value={"providerBatchRef": batch.provider_batch_ref, "status": batch.status},
        )
    db.flush()
    return {"alreadyExported": False, "batch": _batch_dict(batch, transfers)}


def create_export_batch(
    db: Session,
    *,
    invoice_ids: list[int],
    idempotency_key: str,
    created_by_user_id: int,
    billing_month: str | None = None,
) -> dict[str, Any]:
    """Reserve + dispatch in one call (caller commits between phases in finance_ops)."""
    reserved = reserve_export_batch(
        db,
        invoice_ids=invoice_ids,
        idempotency_key=idempotency_key,
        created_by_user_id=created_by_user_id,
        billing_month=billing_month,
    )
    if reserved.get("alreadyExported"):
        return reserved
    return dispatch_export_batch(db, batch_id=reserved["batch"]["id"], actor_user_id=created_by_user_id)


def _return_invoice_to_queue(db: Session, invoice_id: int) -> None:
    inv = db.get(Invoice, invoice_id)
    if inv and inv.status in (InvoiceStatus.EXPORTING, InvoiceStatus.PAID):
        inv.status = InvoiceStatus.APPROVED
        db.flush()


def sync_batch_status(
    db: Session,
    *,
    batch_id: int,
    actor_user_id: int | None = None,
    allow_paid_transition: bool | None = None,
) -> dict[str, Any]:
    batch = db.get(TherapistPayoutBatch, batch_id)
    if not batch:
        raise ValueError("Batch not found")
    if not batch.provider_batch_ref:
        raise ValueError("Batch has no provider reference")

    release_ok = payout_release_enabled() if allow_paid_transition is None else bool(allow_paid_transition)

    transfers = list(
        db.scalars(select(TherapistPayoutTransfer).where(TherapistPayoutTransfer.batch_id == batch.id)).all()
    )
    provider = get_payout_provider()
    transfer_refs = [t.provider_ref for t in transfers if t.provider_ref]
    status_result = provider.get_status(batch_ref=batch.provider_batch_ref, transfer_refs=transfer_refs)
    ref_map = {t.provider_ref: t for t in transfers if t.provider_ref}

    paid_count = 0
    failed_count = 0
    for item in status_result.transfers:
        ref = item.get("providerRef")
        xfer = ref_map.get(ref) if ref else None
        if not xfer:
            continue
        raw_status = (item.get("status") or status_result.status or "").lower()
        if raw_status == "paid" and release_ok:
            xfer.status = TherapistPayoutTransferStatus.PAID.value
            inv = db.get(Invoice, xfer.invoice_id)
            if inv:
                inv.status = InvoiceStatus.PAID
                inv.paid_amount_inr = xfer.net_inr
            paid_count += 1
        elif raw_status == "paid" and not release_ok:
            xfer.status = TherapistPayoutTransferStatus.PROCESSING.value
        elif raw_status == "failed":
            xfer.status = TherapistPayoutTransferStatus.FAILED.value
            xfer.failure_reason = item.get("message") or "Provider reported failure"
            _return_invoice_to_queue(db, xfer.invoice_id)
            failed_count += 1
        else:
            xfer.status = TherapistPayoutTransferStatus.PROCESSING.value
        db.flush()

    if failed_count and paid_count:
        batch.status = TherapistPayoutBatchStatus.PARTIAL_FAILED.value
    elif failed_count:
        batch.status = TherapistPayoutBatchStatus.FAILED.value
    elif paid_count == len(transfers) and transfers and release_ok:
        batch.status = TherapistPayoutBatchStatus.PAID.value
    else:
        batch.status = TherapistPayoutBatchStatus.PROCESSING.value
    db.flush()

    if actor_user_id:
        log_audit(
            db,
            actor_user_id=actor_user_id,
            action="therapist_payout_batch_status_sync",
            entity_type="therapist_payout_batch",
            entity_id=batch.id,
            new_value={"status": batch.status, "paidCount": paid_count, "failedCount": failed_count},
        )
    return _batch_dict(batch, transfers)
