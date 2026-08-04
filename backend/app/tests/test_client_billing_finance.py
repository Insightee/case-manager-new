"""Finance-side client billing: confirm claims, disputes, late fee, RBAC, receivables."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.seed.demo_seed import run as seed_run

client = TestClient(app)


def _login(email: str) -> dict[str, str]:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "demo123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _invoice_with_lines(parent_headers: dict[str, str]) -> dict | None:
    listed = client.get("/api/v1/parent/billing/invoices", headers=parent_headers).json()
    for inv in listed:
        if inv.get("balanceInr", 0) > 0:
            detail = client.get(
                f"/api/v1/parent/billing/invoices/{inv['id']}", headers=parent_headers
            ).json()
            if detail.get("lines"):
                return detail
    return None


def _submit_claim(parent_h: dict, inv_id: int, amount: float) -> int | None:
    r = client.post(
        f"/api/v1/parent/billing/invoices/{inv_id}/payment-claims",
        headers=parent_h,
        data={"amount_inr": str(amount), "method": "UPI", "reference": "FINANCE-TEST"},
    )
    if r.status_code != 201:
        return None
    return r.json().get("id")


def test_finance_rbac_blocks_parent_and_therapist():
    seed_run()
    parent_h = _login("parent@demo.com")
    therapist_h = _login("therapist@demo.com")
    finance_h = _login("finance@demo.com")

    for headers in (parent_h, therapist_h):
        assert client.post("/api/v1/admin/client-billing/payments/1/confirm", headers=headers).status_code == 403
        assert (
            client.post(
                "/api/v1/admin/client-billing/disputes/1/resolve",
                headers=headers,
                json={"status": "RESOLVED", "resolution": "x"},
            ).status_code
            == 403
        )
        assert (
            client.post(
                "/api/v1/admin/client-billing/invoices/1/late-fee?amount_inr=100",
                headers=headers,
            ).status_code
            == 403
        )

    assert client.get("/api/v1/admin/client-billing/receivables", headers=finance_h).status_code == 200


def test_confirm_claim_idempotent_and_partial_status():
    seed_run()
    parent_h = _login("parent@demo.com")
    finance_h = _login("finance@demo.com")
    detail = _invoice_with_lines(parent_h)
    if not detail:
        return
    inv_id = detail["id"]
    balance = float(detail.get("balanceInr") or 0)
    if balance < 100:
        return
    pay_amt = min(100, balance)
    payment_id = _submit_claim(parent_h, inv_id, pay_amt)
    if not payment_id:
        return

    first = client.post(
        f"/api/v1/admin/client-billing/payments/{payment_id}/confirm", headers=finance_h
    )
    assert first.status_code == 200, first.text
    assert first.json().get("status") == "confirmed"

    after = client.get(f"/api/v1/admin/client-billing/invoices/{inv_id}", headers=finance_h).json()
    if pay_amt < balance - 0.01:
        assert after.get("status", "").lower() == "partially_paid"
    assert float(after.get("amountPaidInr") or 0) >= pay_amt - 0.01

    second = client.post(
        f"/api/v1/admin/client-billing/payments/{payment_id}/confirm", headers=finance_h
    )
    assert second.status_code == 200, second.text
    assert second.json().get("status") == "already_confirmed"


def test_confirm_claim_blocked_when_exceeds_collectible():
    seed_run()
    parent_h = _login("parent@demo.com")
    finance_h = _login("finance@demo.com")
    detail = _invoice_with_lines(parent_h)
    if not detail or len(detail["lines"]) < 2:
        return
    inv_id = detail["id"]
    balance = float(detail.get("balanceInr") or 0)
    if balance <= 0:
        return

    payment_id = _submit_claim(parent_h, inv_id, balance)
    if not payment_id:
        return

    line_ids = [ln["id"] for ln in detail["lines"]]
    client.post(
        f"/api/v1/parent/billing/invoices/{inv_id}/disputes",
        headers=parent_h,
        json={
            "reason_code": "incorrect_amount",
            "message": "Finance test — hold all lines before confirm.",
            "line_ids": line_ids,
        },
    )

    blocked = client.post(
        f"/api/v1/admin/client-billing/payments/{payment_id}/confirm", headers=finance_h
    )
    assert blocked.status_code == 400


def test_resolve_dispute_releases_hold_and_recomputes_collectible():
    seed_run()
    parent_h = _login("parent@demo.com")
    finance_h = _login("finance@demo.com")
    detail = _invoice_with_lines(parent_h)
    if not detail or len(detail["lines"]) < 2:
        return
    inv_id = detail["id"]
    line_id = detail["lines"][0]["id"]

    dispute = client.post(
        f"/api/v1/parent/billing/invoices/{inv_id}/disputes",
        headers=parent_h,
        json={
            "reason_code": "duplicate_billing",
            "message": "Finance resolve test.",
            "line_ids": [line_id],
        },
    )
    assert dispute.status_code == 200, dispute.text
    dispute_id = dispute.json().get("id") or dispute.json().get("ids", [None])[0]
    if not dispute_id:
        return

    held = client.get(f"/api/v1/parent/billing/invoices/{inv_id}", headers=parent_h).json()
    assert float(held.get("heldAmountInr") or 0) > 0

    resolved = client.post(
        f"/api/v1/admin/client-billing/disputes/{dispute_id}/resolve",
        headers=finance_h,
        json={"status": "REJECTED", "resolution": "Line stands — dispute not valid."},
    )
    assert resolved.status_code == 200, resolved.text

    after = client.get(f"/api/v1/parent/billing/invoices/{inv_id}", headers=parent_h).json()
    assert float(after.get("heldAmountInr") or 0) < float(held.get("heldAmountInr") or 0)


def test_late_fee_add_and_reverse():
    seed_run()
    finance_h = _login("finance@demo.com")
    parent_h = _login("parent@demo.com")
    detail = _invoice_with_lines(parent_h)
    if not detail:
        return
    inv_id = detail["id"]
    total_before = float(detail.get("totalInr") or 0)

    add = client.post(
        f"/api/v1/admin/client-billing/invoices/{inv_id}/late-fee?amount_inr=150&finance_note=Test",
        headers=finance_h,
    )
    assert add.status_code == 200, add.text
    line_id = add.json().get("lineId")
    assert line_id

    admin_detail = client.get(f"/api/v1/admin/client-billing/invoices/{inv_id}", headers=finance_h).json()
    assert float(admin_detail.get("totalInr") or 0) >= total_before + 149

    parent_detail = client.get(f"/api/v1/parent/billing/invoices/{inv_id}", headers=parent_h).json()
    assert any((ln.get("lineItemType") or "").upper() == "LATE_FEE" for ln in parent_detail.get("lines") or [])

    rem = client.delete(
        f"/api/v1/admin/client-billing/invoices/{inv_id}/lines/{line_id}/late-fee",
        headers=finance_h,
    )
    assert rem.status_code == 200, rem.text


def test_receivables_and_payment_reminder():
    seed_run()
    finance_h = _login("finance@demo.com")
    parent_h = _login("parent@demo.com")

    rec = client.get("/api/v1/admin/client-billing/receivables", headers=finance_h)
    assert rec.status_code == 200, rec.text
    body = rec.json()
    assert "totals" in body
    assert "invoices" in body
    assert "billedInr" in body["totals"]

    detail = _invoice_with_lines(parent_h)
    if not detail or float(detail.get("balanceInr") or 0) <= 0:
        return
    reminder = client.post(
        f"/api/v1/admin/client-billing/invoices/{detail['id']}/payment-reminder",
        headers=finance_h,
    )
    assert reminder.status_code == 200, reminder.text
    assert reminder.json().get("status") == "sent"


def test_zoho_push_noop_when_not_configured():
    seed_run()
    finance_h = _login("finance@demo.com")
    parent_h = _login("parent@demo.com")
    detail = _invoice_with_lines(parent_h)
    if not detail:
        return
    push = client.post(
        f"/api/v1/admin/client-billing/invoices/{detail['id']}/push-zoho",
        headers=finance_h,
    )
    assert push.status_code == 200, push.text
    assert push.json().get("status") in ("not_configured", "already_synced", "attempted")
