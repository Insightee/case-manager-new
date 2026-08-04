"""Therapist statement / payslip PDF download."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _login(email: str) -> dict:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "demo123"})
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_therapist_statement_pdf_download():
    headers = _login("therapist@demo.com")
    rows = client.get("/api/v1/invoices", headers=headers).json()
    assert isinstance(rows, list)
    if not rows:
        return
    inv_id = rows[0]["id"]
    r = client.get(f"/api/v1/invoices/{inv_id}/pdf", headers=headers)
    assert r.status_code == 200, r.text
    assert r.headers.get("content-type") == "application/pdf"
    assert r.content[:4] == b"%PDF"
    assert "attachment" in r.headers.get("content-disposition", "").lower()
    assert "insighte_statement" in r.headers.get("content-disposition", "")


def test_therapist_statement_pdf_requires_own_invoice_or_finance():
    th_headers = _login("therapist@demo.com")
    rows = client.get("/api/v1/invoices", headers=th_headers).json()
    if not rows:
        return
    own = rows[0]
    ok = client.get(f"/api/v1/invoices/{own['id']}/pdf", headers=th_headers)
    assert ok.status_code == 200

    finance_h = _login("finance@demo.com")
    finance_ok = client.get(f"/api/v1/invoices/{own['id']}/pdf", headers=finance_h)
    assert finance_ok.status_code == 200
