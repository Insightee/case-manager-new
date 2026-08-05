"""Dispute → grievance flow E2E — ticket auto-create, finance reply, correction resolve."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import settings
from app.core.database import SessionLocal
from app.main import app
from app.models.client_billing import BillingDispute, BillingDisputeStatus, ClientInvoice, ClientInvoiceLine
from app.models.case import Case
from app.models.support_ticket import TicketMessage
from app.seed.finance_walkthrough_fixture import BILLING_MONTH, run as fixture_run

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def _seed_fixture():
    fixture_run(force=True)
    yield


@pytest.fixture(autouse=True)
def _enable_writes(monkeypatch):
    monkeypatch.setattr(settings, "billing_ledger_writes", True)
    monkeypatch.setattr(settings, "billing_dispute_legacy_adjustment", False)


def _login(email: str) -> dict[str, str]:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "demo123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _wk_invoice(code: str) -> tuple[int, int | None]:
    db = SessionLocal()
    try:
        case = db.scalar(select(Case).where(Case.case_code == code))
        assert case is not None
        inv = db.scalar(
            select(ClientInvoice).where(ClientInvoice.case_id == case.id, ClientInvoice.billing_month == BILLING_MONTH)
        )
        assert inv is not None
        line = db.scalar(
            select(ClientInvoiceLine).where(ClientInvoiceLine.client_invoice_id == inv.id).order_by(ClientInvoiceLine.id)
        )
        return inv.id, line.id if line else None
    finally:
        db.close()


def test_dispute_create_auto_links_support_ticket():
    inv_id, line_id = _wk_invoice("IC-WK-009")
    parent_headers = _login("parent@demo.com")
    dispute = client.post(
        f"/api/v1/parent/billing/invoices/{inv_id}/disputes",
        headers=parent_headers,
        json={
            "reason_code": "incorrect_amount",
            "message": "Walkthrough grievance: session amount looks high for IC-WK-009.",
            "line_ids": [line_id],
        },
    )
    assert dispute.status_code == 200, dispute.text
    body = dispute.json()
    assert body.get("supportTicketId")

    db = SessionLocal()
    try:
        row = db.get(BillingDispute, body["id"])
        assert row is not None
        assert row.support_ticket_id == body["supportTicketId"]
    finally:
        db.close()


def test_finance_public_reply_visible_to_parent():
    inv_id, line_id = _wk_invoice("IC-WK-008")
    parent_headers = _login("parent@demo.com")
    dispute = client.post(
        f"/api/v1/parent/billing/invoices/{inv_id}/disputes",
        headers=parent_headers,
        json={
            "reason_code": "incorrect_amount",
            "message": "Grievance flow test on paid-up case line.",
            "line_ids": [line_id],
        },
    )
    assert dispute.status_code == 200, dispute.text
    ticket_id = dispute.json()["supportTicketId"]
    finance_headers = _login("finance@demo.com")
    reply = client.post(
        f"/api/v1/tickets/{ticket_id}/messages",
        headers=finance_headers,
        json={"body": "Finance desk: we are reviewing your billing concern.", "is_internal": False},
    )
    assert reply.status_code == 201, reply.text

    ticket = client.get(f"/api/v1/tickets/{ticket_id}", headers=parent_headers)
    assert ticket.status_code == 200, ticket.text
    bodies = [m["body"] for m in ticket.json().get("messages", []) if not m.get("isInternal")]
    assert any("Finance desk" in b for b in bodies)


def test_correction_approve_resolves_dispute_and_recomputes_collectible(monkeypatch):
    inv_id, line_id = _wk_invoice("IC-WK-001")
    parent_headers = _login("parent@demo.com")
    finance_headers = _login("finance@demo.com")

    before = client.get(f"/api/v1/parent/billing/invoices/{inv_id}", headers=parent_headers).json()
    held_before = before.get("heldAmountInr", 0)

    dispute = client.post(
        f"/api/v1/parent/billing/invoices/{inv_id}/disputes",
        headers=parent_headers,
        json={
            "reason_code": "incorrect_amount",
            "message": "Re-dispute for correction path on IC-WK-001.",
            "line_ids": [line_id],
        },
    )
    assert dispute.status_code == 200, dispute.text
    dispute_id = dispute.json()["id"]

    after_dispute = client.get(f"/api/v1/parent/billing/invoices/{inv_id}", headers=parent_headers).json()
    assert after_dispute.get("heldAmountInr", 0) >= held_before

    prop = client.post(
        f"/api/v1/admin/client-billing/disputes/{dispute_id}/correction-proposal",
        headers=finance_headers,
        json={"wrong_side": "INVOICE_WRONG", "reason": "Fixture: align invoice to engine after dispute"},
    )
    assert prop.status_code == 200, prop.text
    pid = prop.json()["id"]
    approved = client.post(
        f"/api/v1/admin/finance-writable/corrections/{pid}/approve",
        headers=finance_headers,
        json={},
    )
    assert approved.status_code == 200, approved.text

    db = SessionLocal()
    try:
        row = db.get(BillingDispute, dispute_id)
        assert row is not None
        assert row.status == BillingDisputeStatus.RESOLVED
    finally:
        db.close()

    after = client.get(f"/api/v1/parent/billing/invoices/{inv_id}", headers=parent_headers).json()
    assert after.get("heldAmountInr", 0) == 0


def test_zoho_update_called_on_correction_approve(monkeypatch):
    calls: list[str] = []

    class StubBookkeeping:
        def update_client_invoice(self, invoice_id, *, payload=None, db=None):
            calls.append(f"update:{invoice_id}")
            from app.services.bookkeeping_provider import BookkeepingPushResult

            return BookkeepingPushResult(status="updated", message="stub", external_id=f"ZOHO-{invoice_id}")

        def push_client_invoice(self, *a, **k):
            from app.services.bookkeeping_provider import BookkeepingPushResult

            return BookkeepingPushResult(status="attempted", message="stub", external_id="ZOHO-NEW")

        def push_client_payment(self, *a, **k):
            from app.services.bookkeeping_provider import BookkeepingPushResult

            return BookkeepingPushResult(status="not_configured", message="stub", external_id=None)

    monkeypatch.setattr("app.services.bookkeeping_provider.get_bookkeeping_provider", lambda: StubBookkeeping())
    monkeypatch.setattr(settings, "zoho_books_live_push", True)
    monkeypatch.setattr(settings, "zoho_books_api_key", "test-key")

    inv_id, line_id = _wk_invoice("IC-WK-002")
    parent_headers = _login("parent@demo.com")
    finance_headers = _login("finance@demo.com")
    dispute = client.post(
        f"/api/v1/parent/billing/invoices/{inv_id}/disputes",
        headers=parent_headers,
        json={
            "reason_code": "incorrect_amount",
            "message": "Zoho update path test dispute.",
            "line_ids": [line_id],
        },
    )
    assert dispute.status_code == 200, dispute.text
    dispute_id = dispute.json()["id"]
    prop = client.post(
        f"/api/v1/admin/client-billing/disputes/{dispute_id}/correction-proposal",
        headers=finance_headers,
        json={"wrong_side": "INVOICE_WRONG", "reason": "Zoho stub correction"},
    )
    assert prop.status_code == 200, prop.text
    pid = prop.json()["id"]
    approved = client.post(
        f"/api/v1/admin/finance-writable/corrections/{pid}/approve",
        headers=finance_headers,
        json={},
    )
    assert approved.status_code == 200, approved.text
    assert any(c.startswith("update:") for c in calls)


def test_held_line_not_in_collectible_until_resolved():
    inv_id, line_id = _wk_invoice("IC-WK-005")
    parent_headers = _login("parent@demo.com")
    detail = client.get(f"/api/v1/parent/billing/invoices/{inv_id}", headers=parent_headers).json()
    total = detail["totalInr"]
    client.post(
        f"/api/v1/parent/billing/invoices/{inv_id}/disputes",
        headers=parent_headers,
        json={
            "reason_code": "incorrect_amount",
            "message": "Hold regression check.",
            "line_ids": [line_id],
        },
    )
    after = client.get(f"/api/v1/parent/billing/invoices/{inv_id}", headers=parent_headers).json()
    held = after.get("heldAmountInr", 0)
    assert held > 0
    assert after.get("collectibleInr", total) <= total - held + 0.01
