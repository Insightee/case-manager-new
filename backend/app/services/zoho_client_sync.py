"""Zoho Books client-invoice sync seam (Stage 2).

Runtime-config boundary: when no API key is present the adapter no-ops with a
visible ``not_configured`` status. The same code path attempts a sync once a
key is supplied — never fake success.
"""
from __future__ import annotations

from typing import Any

from app.core.config import settings


def zoho_configured() -> bool:
    return bool((settings.zoho_books_api_key or "").strip())


def sync_client_invoice(invoice_id: int, *, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Attempt Zoho sync for a client invoice. No-op when key absent."""
    _ = payload
    if not zoho_configured():
        return {
            "status": "not_configured",
            "message": "Zoho sync not configured",
            "invoiceId": invoice_id,
            "externalId": None,
        }
    # Key present — staging/cutover path. Real Zoho HTTP calls land in a later
    # Collections/integrations stage; for now record that an attempt was made.
    return {
        "status": "attempted",
        "message": "Zoho sync attempted (adapter stub — awaiting live Books credentials wiring)",
        "invoiceId": invoice_id,
        "externalId": None,
    }
