"""Payout provider seam — mock Razorpay default; live swaps in via env."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
import secrets

from app.core.config import settings


@dataclass
class PayoutTransferRequest:
    invoice_id: int
    amount_inr: float
    reference: str
    therapist_user_id: int


@dataclass
class PayoutBatchResult:
    success: bool
    provider: str
    batch_ref: str | None
    transfers: list[dict]
    message: str


@dataclass
class PayoutStatusResult:
    success: bool
    batch_ref: str
    status: str
    transfers: list[dict]
    message: str


class PayoutProvider(Protocol):
    def create_batch(self, *, transfers: list[PayoutTransferRequest], idempotency_key: str) -> PayoutBatchResult: ...

    def get_status(self, *, batch_ref: str, transfer_refs: list[str] | None = None) -> PayoutStatusResult: ...


class MockRazorpayPayoutProvider:
    """Deterministic mock — FAIL suffix marks failed transfers."""

    name = "MOCK"

    def create_batch(self, *, transfers: list[PayoutTransferRequest], idempotency_key: str) -> PayoutBatchResult:
        batch_ref = f"MOCK-BATCH-{idempotency_key[:24]}"
        out: list[dict] = []
        for t in transfers:
            fail = (t.reference or "").upper().endswith("FAIL")
            out.append(
                {
                    "invoiceId": t.invoice_id,
                    "providerRef": f"{batch_ref}-INV-{t.invoice_id}",
                    "status": "failed" if fail else "processing",
                    "message": "Mock payout failed" if fail else "Mock payout queued",
                }
            )
        return PayoutBatchResult(
            success=True,
            provider=self.name,
            batch_ref=batch_ref,
            transfers=out,
            message="Mock batch created",
        )

    def get_status(self, *, batch_ref: str, transfer_refs: list[str] | None = None) -> PayoutStatusResult:
        fail_batch = (batch_ref or "").upper().endswith("FAIL")
        transfers_out: list[dict] = []
        for ref in transfer_refs or []:
            fail = fail_batch or (ref or "").upper().endswith("FAIL")
            transfers_out.append(
                {
                    "providerRef": ref,
                    "status": "failed" if fail else "paid",
                    "message": "Mock payout failed" if fail else "Mock payout paid",
                }
            )
        if not transfers_out:
            fail = fail_batch
            transfers_out = [
                {
                    "providerRef": batch_ref,
                    "status": "failed" if fail else "paid",
                    "message": "Mock status pull",
                }
            ]
        any_fail = any(t["status"] == "failed" for t in transfers_out)
        all_paid = all(t["status"] == "paid" for t in transfers_out)
        batch_status = "failed" if any_fail and not all_paid else ("paid" if all_paid else "processing")
        return PayoutStatusResult(
            success=True,
            batch_ref=batch_ref,
            status=batch_status,
            transfers=transfers_out,
            message="Mock status",
        )


class RazorpayPayoutProvider:
    name = "RAZORPAY"

    def create_batch(self, *, transfers: list[PayoutTransferRequest], idempotency_key: str) -> PayoutBatchResult:
        batch_ref = f"RZP-STUB-{secrets.token_hex(6).upper()}"
        return PayoutBatchResult(
            success=True,
            provider=self.name,
            batch_ref=batch_ref,
            transfers=[
                {
                    "invoiceId": t.invoice_id,
                    "providerRef": f"{batch_ref}-{t.invoice_id}",
                    "status": "processing",
                    "message": "Razorpay stub — wire live API in cutover",
                }
                for t in transfers
            ],
            message="Razorpay stub batch",
        )

    def get_status(self, *, batch_ref: str, transfer_refs: list[str] | None = None) -> PayoutStatusResult:
        return PayoutStatusResult(
            success=True,
            batch_ref=batch_ref,
            status="processing",
            transfers=[],
            message="Razorpay stub status",
        )


def get_payout_provider():
    provider = (getattr(settings, "payout_provider", None) or "MOCK").strip().upper()
    live = bool(getattr(settings, "payout_provider_live", False))
    if provider == "RAZORPAY" and live:
        return RazorpayPayoutProvider()
    return MockRazorpayPayoutProvider()
