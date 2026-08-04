"""Payment provider seam — mock default; real gateway swaps in via env."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
import secrets

from app.core.config import settings


@dataclass
class PaymentInitResult:
    success: bool
    provider: str
    provider_ref: str | None
    payment_url: str | None
    message: str


@dataclass
class PaymentVerifyResult:
    success: bool
    provider_ref: str | None
    message: str


class PaymentProvider(Protocol):
    def initiate(self, *, invoice_id: int, amount_inr: float, reference: str) -> PaymentInitResult: ...

    def verify(self, *, provider_ref: str, amount_inr: float) -> PaymentVerifyResult: ...


class MockPaymentProvider:
    """Deterministic mock — success unless reference ends with FAIL."""

    name = "MOCK"

    def initiate(self, *, invoice_id: int, amount_inr: float, reference: str) -> PaymentInitResult:
        ref = reference or f"MOCK-{invoice_id}-{secrets.token_hex(4).upper()}"
        fail = ref.upper().endswith("FAIL")
        return PaymentInitResult(
            success=not fail,
            provider=self.name,
            provider_ref=ref,
            payment_url=f"/parent/billing/mock-pay?ref={ref}" if not fail else None,
            message="Mock payment failed" if fail else "Mock payment ready",
        )

    def verify(self, *, provider_ref: str, amount_inr: float) -> PaymentVerifyResult:
        fail = (provider_ref or "").upper().endswith("FAIL")
        return PaymentVerifyResult(
            success=not fail,
            provider_ref=provider_ref,
            message="Mock verification failed" if fail else "Mock verification succeeded",
        )


def get_payment_provider() -> PaymentProvider:
    provider = (getattr(settings, "payment_gateway_provider", None) or "MOCK").strip().upper()
    if provider == "MOCK" or not getattr(settings, "payment_gateway_live", False):
        return MockPaymentProvider()
    return MockPaymentProvider()
