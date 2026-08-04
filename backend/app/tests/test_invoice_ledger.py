"""Therapist statement ledger API."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _login(email: str) -> dict:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "demo123"})
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_therapist_ledger_returns_rows_and_filters():
    headers = _login("therapist@demo.com")
    r = client.get("/api/v1/invoices/ledger", headers=headers)
    assert r.status_code == 200, r.text
    payload = r.json()
    assert "rows" in payload
    assert "filters" in payload
    assert "summary" in payload
    assert isinstance(payload["rows"], list)
    filters = payload["filters"]
    assert "years" in filters
    assert "months" in filters
    assert "clients" in filters
    assert "statuses" in filters
    summary = payload["summary"]
    assert "rowCount" in summary
    assert "netInr" in summary


def test_therapist_ledger_year_filter():
    headers = _login("therapist@demo.com")
    all_rows = client.get("/api/v1/invoices/ledger", headers=headers).json()["rows"]
    if not all_rows:
        return
    year = all_rows[0].get("periodYear")
    if not year:
        return
    filtered = client.get(f"/api/v1/invoices/ledger?year={year}", headers=headers).json()
    assert filtered["summary"]["rowCount"] <= len(all_rows)
    for row in filtered["rows"]:
        assert row.get("periodYear") == year


def test_therapist_ledger_requires_billing_access():
    headers = _login("parent@demo.com")
    r = client.get("/api/v1/invoices/ledger", headers=headers)
    assert r.status_code == 403
