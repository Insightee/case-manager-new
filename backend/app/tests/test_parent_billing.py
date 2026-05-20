"""Parent client billing API tests."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _login(email: str, password: str = "demo123") -> dict:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_parent_billing_dashboard():
    headers = _login("parent@demo.com")
    r = client.get("/api/v1/parent/billing/dashboard", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert "summary" in data
    assert "invoices" in data
    assert "packages" in data
    assert "filterOptions" in data


def test_parent_billing_filters():
    headers = _login("parent@demo.com")
    r = client.get("/api/v1/parent/billing/invoices?payment_bucket=unpaid", headers=headers)
    assert r.status_code == 200
    for inv in r.json():
        assert inv["paymentBucket"] == "unpaid"


def test_parent_billing_needs_payment_bucket():
    headers = _login("parent@demo.com")
    r = client.get("/api/v1/parent/billing/invoices?payment_bucket=needs_payment", headers=headers)
    assert r.status_code == 200
    for inv in r.json():
        assert inv["paymentBucket"] in ("unpaid", "partial")
        assert "isOverdue" in inv


def test_parent_billing_dashboard_overdue_field():
    headers = _login("parent@demo.com")
    r = client.get("/api/v1/parent/billing/dashboard", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert "overdueCount" in data["summary"]
    assert "needsPaymentCount" in data["summary"]
    for inv in data.get("invoices", []):
        assert "isOverdue" in inv


def test_parent_invoice_detail_and_dispute():
    headers = _login("parent@demo.com")
    dash = client.get("/api/v1/parent/billing/dashboard", headers=headers).json()
    unpaid = [i for i in dash.get("invoices", []) if i.get("paymentBucket") == "unpaid"]
    if not unpaid:
        return
    inv_id = unpaid[0]["id"]
    detail = client.get(f"/api/v1/parent/billing/invoices/{inv_id}", headers=headers)
    assert detail.status_code == 200
    assert detail.json().get("lines") is not None
    if detail.json()["lines"]:
        line_id = detail.json()["lines"][0]["id"]
        sess = client.get(f"/api/v1/parent/billing/lines/{line_id}/session", headers=headers)
        assert sess.status_code == 200
        assert "session_notes" not in sess.json()


def test_admin_record_payment():
    parent_h = _login("parent@demo.com")
    admin_h = _login("superadmin@demo.com")
    dash = client.get("/api/v1/parent/billing/dashboard", headers=parent_h).json()
    unpaid = [i for i in dash.get("invoices", []) if i.get("balanceInr", 0) > 0]
    if not unpaid:
        return
    inv_id = unpaid[0]["id"]
    amt = min(500, unpaid[0]["balanceInr"])
    r = client.post(
        f"/api/v1/admin/client-billing/invoices/{inv_id}/payments",
        headers=admin_h,
        json={"amount_inr": amt, "method": "UPI", "reference": "TEST-PAY-1"},
    )
    assert r.status_code == 200


def test_admin_notify_parent_invoice():
    parent_h = _login("parent@demo.com")
    admin_h = _login("superadmin@demo.com")
    dash = client.get("/api/v1/parent/billing/dashboard", headers=parent_h).json()
    invs = dash.get("invoices") or []
    if not invs:
        return
    inv_id = invs[0]["id"]
    r = client.post(
        f"/api/v1/admin/client-billing/invoices/{inv_id}/notify-parent?resend=true",
        headers=admin_h,
    )
    assert r.status_code == 200
    assert r.json().get("status") in ("sent", "already_sent")
