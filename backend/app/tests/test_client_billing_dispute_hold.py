"""Per-line dispute hold: collectible balance excludes held lines; invoice stays payable."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app.main import app
from app.models.client_billing import BillingDisputeStatus, ClientInvoice, ClientInvoiceStatus
from app.seed.demo_seed import run as seed_run

client = TestClient(app)


def _login(email: str) -> dict[str, str]:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "demo123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _first_unpaid_invoice(headers: dict[str, str]) -> dict | None:
    dash = client.get("/api/v1/parent/billing/dashboard", headers=headers).json()
    for inv in dash.get("invoices") or []:
        if inv.get("balanceInr", 0) > 0 and inv.get("lines") is None:
            detail = client.get(f"/api/v1/parent/billing/invoices/{inv['id']}", headers=headers).json()
            if detail.get("lines"):
                return detail
    listed = client.get("/api/v1/parent/billing/invoices", headers=headers).json()
    for inv in listed:
        if inv.get("balanceInr", 0) > 0:
            detail = client.get(f"/api/v1/parent/billing/invoices/{inv['id']}", headers=headers).json()
            if detail.get("lines"):
                return detail
    return None


def test_dispute_holds_line_not_whole_invoice():
    seed_run()
    headers = _login("parent@demo.com")
    detail = _first_unpaid_invoice(headers)
    if not detail or len(detail["lines"]) < 2:
        return
    inv_id = detail["id"]
    line_id = detail["lines"][0]["id"]
    held_amount = detail["lines"][0]["amountInr"]
    total = detail["totalInr"]

    dispute = client.post(
        f"/api/v1/parent/billing/invoices/{inv_id}/disputes",
        headers=headers,
        json={
            "reason_code": "incorrect_amount",
            "message": "This session amount looks wrong for dispute-hold test.",
            "line_ids": [line_id],
        },
    )
    assert dispute.status_code == 200, dispute.text

    after = client.get(f"/api/v1/parent/billing/invoices/{inv_id}", headers=headers).json()
    assert after["status"] != "disputed"
    assert after.get("hasDispute") is True
    assert after.get("heldAmountInr", 0) >= held_amount - 0.01
    expected_collectible = max(0, total - held_amount)
    assert after.get("collectibleInr", 0) <= expected_collectible + 0.01
    assert after.get("balanceInr", 0) <= expected_collectible + 0.01

    held_lines = [ln for ln in after["lines"] if ln.get("isHeld")]
    assert any(ln["id"] == line_id for ln in held_lines)

    db = SessionLocal()
    try:
        inv = db.get(ClientInvoice, inv_id)
        assert inv is not None
        assert inv.status != ClientInvoiceStatus.DISPUTED
    finally:
        db.close()


def test_partial_dispute_allows_payment_on_remainder():
    headers = _login("parent@demo.com")
    detail = _first_unpaid_invoice(headers)
    if not detail or len(detail["lines"]) < 2:
        return
    inv_id = detail["id"]
    line_id = detail["lines"][0]["id"]
    client.post(
        f"/api/v1/parent/billing/invoices/{inv_id}/disputes",
        headers=headers,
        json={
            "reason_code": "duplicate_billing",
            "message": "Duplicate session line for partial-pay test.",
            "line_ids": [line_id],
        },
    )
    after = client.get(f"/api/v1/parent/billing/invoices/{inv_id}", headers=headers).json()
    collectible = after.get("collectibleInr") or after.get("balanceInr") or 0
    if collectible <= 0:
        return
    pay_amt = min(100, collectible)
    claim = client.post(
        f"/api/v1/parent/billing/invoices/{inv_id}/payment-claims",
        headers=headers,
        data={"amount_inr": str(pay_amt), "method": "UPI", "reference": "DISPUTE-HOLD-TEST"},
    )
    assert claim.status_code == 201, claim.text
    assert claim.json().get("paymentStatus") == "pending_review"
