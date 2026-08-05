"""Therapist payout batch export, idempotency, and status sync."""
from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.audit import log_audit
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


def create_export_batch(
    db: Session,
    *,
    invoice_ids: list[int],
    idempotency_key: str,
    created_by_user_id: int,
    billing_month: str | None = None,
) -> dict[str, Any]:
    key = (idempotency_key or "").strip()
    if not key:
        raise ValueError("Idempotency key is required")
    if not invoice_ids:
        raise ValueError("Select at least one approved statement")

    existing = get_batch_by_idempotency(db, key)
    if existing:
        transfers = list(
            db.scalars(select(TherapistPayoutTransfer).where(TherapistPayoutTransfer.batch_id == existing.id)).all()
        )
        return {"alreadyExported": True, "batch": _batch_dict(existing, transfers)}

    invoices: list[Invoice] = []
    settlements: list[dict[str, Any]] = []
    for iid in sorted(set(invoice_ids)):
        inv = db.get(Invoice, iid)
        if not inv:
            raise ValueError(f"Invoice {iid} not found")
        if inv.status != InvoiceStatus.APPROVED:
            raise ValueError(f"Invoice {iid} must be APPROVED before export")
        settlement = payout_settlement_service.assert_exportable(db, inv)
        invoices.append(inv)
        settlements.append(settlement)

    month = billing_month or (invoices[0].month if invoices else "")
    provider = get_payout_provider()
    xfer_requests = [
        PayoutTransferRequest(
            invoice_id=inv.id,
            amount_inr=sett["netInr"],
            reference=f"PAYOUT-{inv.id}",
            therapist_user_id=inv.therapist_user_id,
        )
        for inv, sett in zip(invoices, settlements)
    ]
    result = provider.create_batch(transfers=xfer_requests, idempotency_key=key)

    batch = TherapistPayoutBatch(
        billing_month=month,
        status=TherapistPayoutBatchStatus.EXPORTED.value,
        provider=result.provider,
        idempotency_key=key,
        provider_batch_ref=result.batch_ref,
        created_by_user_id=created_by_user_id,
    )
    db.add(batch)
    db.flush()

    provider_by_invoice = {t["invoiceId"]: t for t in result.transfers}
    transfer_rows: list[TherapistPayoutTransfer] = []
    for inv, sett in zip(invoices, settlements):
        prov = provider_by_invoice.get(inv.id, {})
        status = TherapistPayoutTransferStatus.PROCESSING.value
        if prov.get("status") == "failed":
            status = TherapistPayoutTransferStatus.FAILED.value
        xfer = TherapistPayoutTransfer(
            batch_id=batch.id,
            invoice_id=inv.id,
            gross_inr=sett["grossInr"],
            tds_rate_percent=sett["tdsRatePercent"],
            tds_inr=sett["tdsInr"],
            deductions_inr=sett["deductionsInr"],
            net_inr=sett["netInr"],
            provider_ref=prov.get("providerRef"),
            status=status,
            failure_reason=prov.get("message") if status == TherapistPayoutTransferStatus.FAILED.value else None,
        )
        db.add(xfer)
        transfer_rows.append(xfer)
        payout_settlement_service.snapshot_settlement_on_invoice(db, inv, sett)
    db.flush()

    external_ref_service.upsert_external_ref(
        db, _PROVIDER, "therapist_payout_batch", batch.id, result.batch_ref or f"BATCH-{batch.id}"
    )
    for xfer in transfer_rows:
        if xfer.provider_ref:
            external_ref_service.upsert_external_ref(
                db, _PROVIDER, "therapist_payout_transfer", xfer.id, xfer.provider_ref
            )

    log_audit(
        db,
        actor_user_id=created_by_user_id,
        action="therapist_payout_batch_exported",
        entity_type="therapist_payout_batch",
        entity_id=batch.id,
        new_value={"invoiceIds": invoice_ids, "idempotencyKey": key},
    )
    db.flush()
    return {"alreadyExported": False, "batch": _batch_dict(batch, transfer_rows)}


def _return_invoice_to_queue(db: Session, invoice_id: int) -> None:
    inv = db.get(Invoice, invoice_id)
    if inv and inv.status != InvoiceStatus.APPROVED:
        inv.status = InvoiceStatus.APPROVED
        db.flush()


def sync_batch_status(db: Session, *, batch_id: int, actor_user_id: int | None = None) -> dict[str, Any]:
    batch = db.get(TherapistPayoutBatch, batch_id)
    if not batch:
        raise ValueError("Batch not found")
    if not batch.provider_batch_ref:
        raise ValueError("Batch has no provider reference")

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
        if raw_status == "paid":
            xfer.status = TherapistPayoutTransferStatus.PAID.value
            inv = db.get(Invoice, xfer.invoice_id)
            if inv:
                inv.status = InvoiceStatus.PAID
                inv.paid_amount_inr = xfer.net_inr
            paid_count += 1
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
    elif paid_count == len(transfers) and transfers:
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
