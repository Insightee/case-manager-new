from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.seed.demo_seed import run as seed_run

client = TestClient(app)


def setup_module():
    seed_run()


def _headers(email: str = "superadmin@demo.com") -> dict:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "demo123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_collections_uses_payment_status_and_paginates():
    headers = _headers()
    r = client.get(
        "/api/v1/admin/finance-reports/collections?billing_month=2026-10&page=1&page_size=50",
        headers=headers,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["count"] >= len(data["rows"])
    assert data.get("previewLimited") == (len(data["rows"]) < data["count"])
    assert "confirmedTotalInr" in data
    for row in data["rows"]:
        assert "paymentStatus" in row
        assert "status" not in row or row.get("paymentStatus")


def test_payout_preview_does_not_run_until_requested():
    headers = _headers()
    r = client.get(
        "/api/v1/admin/finance-reports/therapist-payout-preview?billing_month=2026-10&page=1&page_size=50",
        headers=headers,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["reportKey"] == "therapist-payout-preview"
    assert "count" in data
    assert data.get("pageSize") == 50
    assert len(data["rows"]) <= 50
    if data["count"] > 50:
        assert data["previewLimited"] is True
