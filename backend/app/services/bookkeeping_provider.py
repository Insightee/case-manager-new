"""Bookkeeping provider seam — no-op default; Zoho Books when configured."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from app.core.config import settings


@dataclass
class BookkeepingPushResult:
    status: str
    message: str
    external_id: str | None


class BookkeepingProvider(Protocol):
    def push_client_invoice(
        self, invoice_id: int, *, payload: dict[str, Any] | None = None, db=None
    ) -> BookkeepingPushResult: ...

    def push_client_payment(
        self, payment_id: int, *, payload: dict[str, Any] | None = None, db=None
    ) -> BookkeepingPushResult: ...


class NoOpBookkeepingProvider:
    name = "NOOP"

    def push_client_invoice(
        self, invoice_id: int, *, payload: dict[str, Any] | None = None, db=None
    ) -> BookkeepingPushResult:
        return BookkeepingPushResult(
            status="not_configured",
            message="Bookkeeping sync not configured",
            external_id=None,
        )

    def push_client_payment(
        self, payment_id: int, *, payload: dict[str, Any] | None = None, db=None
    ) -> BookkeepingPushResult:
        return BookkeepingPushResult(
            status="not_configured",
            message="Bookkeeping sync not configured",
            external_id=None,
        )


class ZohoBookkeepingProvider:
    name = "ZOHO_BOOKS"

    def push_client_invoice(self, invoice_id: int, *, payload: dict[str, Any] | None = None, db=None) -> BookkeepingPushResult:
        from app.services import external_ref_service, zoho_client_sync

        if not zoho_client_sync.zoho_configured():
            return BookkeepingPushResult(status="not_configured", message="Zoho not configured", external_id=None)
        if db is not None:
            existing = external_ref_service.get_external_id_db(db, "ZOHO_BOOKS", "client_invoice", invoice_id)
        else:
            existing = None
        if existing:
            return BookkeepingPushResult(status="already_synced", message="Existing Zoho id reused", external_id=existing)
        out = zoho_client_sync.sync_client_invoice(invoice_id, payload=payload)
        ext = out.get("externalId") or f"ZOHO-STUB-{invoice_id}"
        if db is not None and ext:
            external_ref_service.upsert_external_ref(db, "ZOHO_BOOKS", "client_invoice", invoice_id, ext)
        return BookkeepingPushResult(
            status=out.get("status", "attempted"),
            message=out.get("message", ""),
            external_id=ext,
        )

    def push_client_payment(
        self, payment_id: int, *, payload: dict[str, Any] | None = None, db=None
    ) -> BookkeepingPushResult:
        from app.services import external_ref_service, zoho_client_sync

        if not zoho_client_sync.zoho_configured():
            return BookkeepingPushResult(status="not_configured", message="Zoho not configured", external_id=None)
        if db is not None:
            existing = external_ref_service.get_external_id_db(db, "ZOHO_BOOKS", "client_payment", payment_id)
        else:
            existing = None
        if existing:
            return BookkeepingPushResult(status="already_synced", message="Existing Zoho id reused", external_id=existing)
        return BookkeepingPushResult(
            status="attempted",
            message="Zoho payment push stub — awaiting live Books credentials wiring",
            external_id=f"ZOHO-PAY-STUB-{payment_id}",
        )


def get_bookkeeping_provider() -> BookkeepingProvider:
    if not getattr(settings, "zoho_books_live_push", False) or not (settings.zoho_books_api_key or "").strip():
        return NoOpBookkeepingProvider()
    return ZohoBookkeepingProvider()
