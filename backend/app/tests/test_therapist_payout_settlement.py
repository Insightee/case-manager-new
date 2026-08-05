"""Therapist payout settlement E2E — IC-WK-011..014 fixture cases."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import settings
from app.core.database import SessionLocal
from app.main import app
from app.models.external_ref import ExternalRef
from app.models.invoice import Invoice, InvoiceStatus
from app.models.invoice_line import InvoiceCaseLine
from app.models.therapist_payout_settlement import TherapistPayoutBatch, TherapistPayoutTransfer
from app.seed.finance_walkthrough_fixture import BILLING_MONTH, run as fixture_run

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def _seed_finance_walkthrough_fixture():
    fixture_run(force=True)
    yield


@pytest.fixture(autouse=True)
def _enable_payout_flags(monkeypatch):
    monkeypatch.setattr(settings, "billing_ledger_writes", True)
    monkeypatch.setattr(settings, "payout_export_enabled", True)
    monkeypatch.setattr(settings, "payout_release_enabled", False)


def _login(email: str) -> dict[str, str]:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "demo123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _invoice_for_case(code: str) -> int:
    db = SessionLocal()
    try:
        case_line = db.scalar(
            select(InvoiceCaseLine)
            .join(Invoice, InvoiceCaseLine.invoice_id == Invoice.id)
            .where(InvoiceCaseLine.case_code == code, Invoice.month == BILLING_MONTH)
            .order_by(Invoice.id.desc())
        )
        assert case_line is not None, f"No therapist invoice for {code}"
        return case_line.invoice_id
    finally:
        db.close()


def test_settlement_preview_ic_wk_011():
    inv_id = _invoice_for_case("IC-WK-011")
    headers = _login("finance@demo.com")
    preview = client.get(
        f"/api/v1/admin/therapist-payouts/settlement-preview?invoice_id={inv_id}",
        headers=headers,
    )
    assert preview.status_code == 200, preview.text
    body = preview.json()
    assert body["grossInr"] == 10000.0
    assert body["tdsInr"] == 1000.0
    assert body["netInr"] == 9000.0
    assert body["blocked"] is False


def test_settlement_preview_ic_wk_012_nonround_tds():
    inv_id = _invoice_for_case("IC-WK-012")
    headers = _login("finance@demo.com")
    preview = client.get(
        f"/api/v1/admin/therapist-payouts/settlement-preview?invoice_id={inv_id}",
        headers=headers,
    )
    assert preview.status_code == 200, preview.text
    body = preview.json()
    assert body["grossInr"] == 3333.0
    assert body["tdsInr"] == 333.3
    assert body["netInr"] == 2999.7


def test_settlement_preview_ic_wk_013_deduction():
    inv_id = _invoice_for_case("IC-WK-013")
    headers = _login("finance@demo.com")
    preview = client.get(
        f"/api/v1/admin/therapist-payouts/settlement-preview?invoice_id={inv_id}",
        headers=headers,
    )
    assert preview.status_code == 200, preview.text
    body = preview.json()
    assert body["grossInr"] == 10000.0
    assert body["deductionsInr"] == 500.0
    assert body["netInr"] == 8500.0


def test_ic_wk_014_blocks_export():
    inv_id = _invoice_for_case("IC-WK-014")
    headers = _login("finance@demo.com")
    preview = client.get(
        f"/api/v1/admin/therapist-payouts/settlement-preview?invoice_id={inv_id}",
        headers=headers,
    )
    assert preview.status_code == 200, preview.text
    assert preview.json()["blocked"] is True

    export = client.post(
        "/api/v1/admin/therapist-payouts/export-batch",
        headers=headers,
        json={"invoice_ids": [inv_id], "idempotency_key": "wk-014-blocked-export"},
    )
    assert export.status_code == 400


def test_mock_export_creates_transfers_and_external_refs():
    inv_id = _invoice_for_case("IC-WK-013")
    headers = _login("finance@demo.com")
    key = "wk-013-export-001"
    export = client.post(
        "/api/v1/admin/therapist-payouts/export-batch",
        headers=headers,
        json={"invoice_ids": [inv_id], "idempotency_key": key, "billing_month": BILLING_MONTH},
    )
    assert export.status_code == 200, export.text
    batch = export.json()["batch"]
    assert batch["transferCount"] == 1
    assert export.json()["alreadyExported"] is False

    db = SessionLocal()
    try:
        xfer = db.scalar(select(TherapistPayoutTransfer).where(TherapistPayoutTransfer.invoice_id == inv_id))
        assert xfer is not None
        ext = db.scalar(
            select(ExternalRef).where(
                ExternalRef.provider == "RAZORPAY_PAYOUT",
                ExternalRef.entity_type == "therapist_payout_transfer",
                ExternalRef.entity_id == xfer.id,
            )
        )
        assert ext is not None
    finally:
        db.close()


def test_idempotent_reexport_same_key():
    inv_id = _invoice_for_case("IC-WK-012")
    headers = _login("finance@demo.com")
    key = "wk-012-idempotent"
    first = client.post(
        "/api/v1/admin/therapist-payouts/export-batch",
        headers=headers,
        json={"invoice_ids": [inv_id], "idempotency_key": key},
    )
    assert first.status_code == 200, first.text
    second = client.post(
        "/api/v1/admin/therapist-payouts/export-batch",
        headers=headers,
        json={"invoice_ids": [inv_id], "idempotency_key": key},
    )
    assert second.status_code == 200, second.text
    assert second.json()["alreadyExported"] is True

    db = SessionLocal()
    try:
        batches = db.scalars(select(TherapistPayoutBatch).where(TherapistPayoutBatch.idempotency_key == key)).all()
        assert len(batches) == 1
        transfers = db.scalars(select(TherapistPayoutTransfer).where(TherapistPayoutTransfer.invoice_id == inv_id)).all()
        assert len(transfers) == 1
    finally:
        db.close()


def test_status_sync_marks_paid():
    inv_id = _invoice_for_case("IC-WK-012")
    headers = _login("finance@demo.com")
    key = "wk-012-sync-paid"
    export = client.post(
        "/api/v1/admin/therapist-payouts/export-batch",
        headers=headers,
        json={"invoice_ids": [inv_id], "idempotency_key": key},
    )
    assert export.status_code == 200, export.text
    batch_id = export.json()["batch"]["id"]
    sync = client.post(f"/api/v1/admin/therapist-payouts/batches/{batch_id}/sync-status", headers=headers)
    assert sync.status_code == 200, sync.text
    assert sync.json()["status"] == "PAID"

    db = SessionLocal()
    try:
        inv = db.get(Invoice, inv_id)
        assert inv is not None
        assert inv.status == InvoiceStatus.PAID
    finally:
        db.close()


def test_mock_failure_returns_invoice_to_queue(monkeypatch):
    inv_id = _invoice_for_case("IC-WK-011")
    headers = _login("finance@demo.com")

    from app.services import payout_provider

    class FailXferMock(payout_provider.MockRazorpayPayoutProvider):
        def create_batch(self, *, transfers, idempotency_key):
            result = super().create_batch(transfers=transfers, idempotency_key=idempotency_key)
            result.transfers = [
                {**t, "status": "failed", "providerRef": f"{t['providerRef']}-FAIL"}
                for t in result.transfers
            ]
            return result

    monkeypatch.setattr("app.services.payout_batch_service.get_payout_provider", lambda: FailXferMock())

    key = "wk-011-fail-return"
    export = client.post(
        "/api/v1/admin/therapist-payouts/export-batch",
        headers=headers,
        json={"invoice_ids": [inv_id], "idempotency_key": key},
    )
    assert export.status_code == 200, export.text
    batch_id = export.json()["batch"]["id"]
    sync = client.post(f"/api/v1/admin/therapist-payouts/batches/{batch_id}/sync-status", headers=headers)
    assert sync.status_code == 200, sync.text

    db = SessionLocal()
    try:
        inv = db.get(Invoice, inv_id)
        assert inv is not None
        assert inv.status == InvoiceStatus.APPROVED
        xfer = db.scalar(
            select(TherapistPayoutTransfer)
            .where(TherapistPayoutTransfer.invoice_id == inv_id)
            .order_by(TherapistPayoutTransfer.id.desc())
        )
        assert xfer is not None
        assert xfer.status == "FAILED"
    finally:
        db.close()


def test_unapproved_statement_export_rejected():
    db = SessionLocal()
    try:
        inv = db.scalar(select(Invoice).where(Invoice.status == InvoiceStatus.IN_REVIEW).limit(1))
        assert inv is not None
        inv_id = inv.id
    finally:
        db.close()
    headers = _login("finance@demo.com")
    export = client.post(
        "/api/v1/admin/therapist-payouts/export-batch",
        headers=headers,
        json={"invoice_ids": [inv_id], "idempotency_key": "unapproved-block"},
    )
    assert export.status_code == 400
