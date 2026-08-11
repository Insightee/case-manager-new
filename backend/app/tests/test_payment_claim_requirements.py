"""Offline parent payment claims require reference, payment date, and proof."""

from __future__ import annotations

from io import BytesIO

from fastapi.testclient import TestClient

from app.main import app
from app.seed.demo_seed import run as seed_run

client = TestClient(app)

MINIMAL_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\xcf"
    b"\xc0\x00\x00\x00\x03\x00\x01\x00\x05\xfe\xd4\xef\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _login(email: str) -> dict[str, str]:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "demo123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _unpaid_invoice(headers: dict[str, str]) -> dict | None:
    listed = client.get("/api/v1/parent/billing/invoices", headers=headers).json()
    for inv in listed:
        if inv.get("balanceInr", 0) > 0:
            detail = client.get(f"/api/v1/parent/billing/invoices/{inv['id']}", headers=headers).json()
            if detail.get("lines"):
                return detail
    return None


def _claim_files():
    return {"proof": ("payment-proof.png", BytesIO(MINIMAL_PNG), "image/png")}


def test_payment_claim_requires_reference_proof_and_date():
    seed_run()
    parent_h = _login("parent@demo.com")
    detail = _unpaid_invoice(parent_h)
    if not detail:
        return
    inv_id = detail["id"]
    amount = min(100.0, float(detail.get("balanceInr") or 0))
    if amount <= 0:
        return

    missing_ref = client.post(
        f"/api/v1/parent/billing/invoices/{inv_id}/payment-claims",
        headers=parent_h,
        data={"amount_inr": str(amount), "method": "UPI", "reference": " ", "payment_date": "2026-05-10"},
        files=_claim_files(),
    )
    assert missing_ref.status_code == 400

    missing_proof = client.post(
        f"/api/v1/parent/billing/invoices/{inv_id}/payment-claims",
        headers=parent_h,
        data={"amount_inr": str(amount), "method": "UPI", "reference": "REF-123", "payment_date": "2026-05-10"},
    )
    assert missing_proof.status_code == 422

    missing_date = client.post(
        f"/api/v1/parent/billing/invoices/{inv_id}/payment-claims",
        headers=parent_h,
        data={"amount_inr": str(amount), "method": "UPI", "reference": "REF-123"},
        files=_claim_files(),
    )
    assert missing_date.status_code == 422

    ok = client.post(
        f"/api/v1/parent/billing/invoices/{inv_id}/payment-claims",
        headers=parent_h,
        data={
            "amount_inr": str(amount),
            "method": "UPI",
            "reference": "REF-OFFLINE-001",
            "payment_date": "2026-05-10",
            "notes": "Offline UPI test",
        },
        files=_claim_files(),
    )
    assert ok.status_code == 201, ok.text
    payload = ok.json()
    assert payload.get("paymentStatus") == "pending_review"

    finance_h = _login("finance@demo.com")
    claims = client.get("/api/v1/admin/client-billing/payment-claims", headers=finance_h)
    assert claims.status_code == 200
    rows = claims.json()
    assert any(r.get("reference") == "REF-OFFLINE-001" and r.get("method") == "UPI" for r in rows)

    payment_id = payload["id"]
    proof = client.get(f"/api/v1/admin/client-billing/payments/{payment_id}/proof", headers=finance_h)
    assert proof.status_code == 200
    assert proof.content[:4] == b"\x89PNG"
