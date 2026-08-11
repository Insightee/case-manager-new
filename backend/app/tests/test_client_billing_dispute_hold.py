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
    from io import BytesIO

    png = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\xcf"
        b"\xc0\x00\x00\x00\x03\x00\x01\x00\x05\xfe\xd4\xef\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    claim = client.post(
        f"/api/v1/parent/billing/invoices/{inv_id}/payment-claims",
        headers=headers,
        data={
            "amount_inr": str(pay_amt),
            "method": "UPI",
            "reference": "DISPUTE-HOLD-TEST",
            "payment_date": "2026-05-10",
        },
        files={"proof": ("proof.png", BytesIO(png), "image/png")},
    )
    assert claim.status_code == 201, claim.text
    assert claim.json().get("paymentStatus") == "pending_review"


def test_all_lines_held_collectible_zero_pay_blocked():
    """When every line is disputed, collectible and balance are 0; pay paths reject."""
    headers = _login("parent@demo.com")
    detail = _first_unpaid_invoice(headers)
    if not detail or not detail.get("lines"):
        return
    inv_id = detail["id"]
    all_line_ids = [ln["id"] for ln in detail["lines"]]
    total = detail["totalInr"]

    dispute = client.post(
        f"/api/v1/parent/billing/invoices/{inv_id}/disputes",
        headers=headers,
        json={
            "reason_code": "incorrect_amount",
            "message": "All session lines disputed for full-hold collectible test.",
            "line_ids": all_line_ids,
        },
    )
    assert dispute.status_code == 200, dispute.text

    after = client.get(f"/api/v1/parent/billing/invoices/{inv_id}", headers=headers).json()
    assert after.get("heldAmountInr", 0) >= total - 0.01
    assert after.get("collectibleInr") == 0
    assert after.get("balanceInr") == 0
    assert all(ln.get("isHeld") for ln in after.get("lines") or [])

    claim = client.post(
        f"/api/v1/parent/billing/invoices/{inv_id}/payment-claims",
        headers=headers,
        data={
            "amount_inr": "100",
            "method": "UPI",
            "reference": "SHOULD-BLOCK",
            "payment_date": "2026-05-10",
        },
        files={"proof": ("proof.png", __import__("io").BytesIO(
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
            b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\xcf"
            b"\xc0\x00\x00\x00\x03\x00\x01\x00\x05\xfe\xd4\xef\x00\x00\x00\x00IEND\xaeB`\x82"
        ), "image/png")},
    )
    assert claim.status_code == 400

    gateway = client.post(f"/api/v1/parent/billing/invoices/{inv_id}/pay-gateway", headers=headers)
    assert gateway.status_code == 400


def test_held_sum_cannot_drive_collectible_negative():
    """Held line totals above invoice total clamp collectible at 0, never negative."""
    from app.models.client_billing import ClientInvoice, ClientInvoiceLine, BillingDispute, BillingDisputeStatus
    from app.services.client_billing_service import _compute_invoice_balances

    inv = ClientInvoice(total_inr=100, amount_paid_inr=0)
    lines = [
        ClientInvoiceLine(id=1, amount_inr=80),
        ClientInvoiceLine(id=2, amount_inr=70),
    ]
    disputes = [
        BillingDispute(client_invoice_line_id=1, status=BillingDisputeStatus.OPEN),
        BillingDispute(client_invoice_line_id=2, status=BillingDisputeStatus.OPEN),
    ]
    amounts = _compute_invoice_balances(inv, lines, disputes)
    assert amounts["heldAmountInr"] == 150
    assert amounts["collectibleInr"] == 0
    assert amounts["balanceInr"] == 0
