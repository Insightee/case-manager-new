from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.seed.demo_seed import run as seed_run

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    seed_run()


def _headers(email: str) -> dict:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "demo123"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_finance_report_monthly_billing_json():
    headers = _headers("finance@demo.com")
    r = client.get("/api/v1/admin/finance-reports/monthly-billing", headers=headers)
    assert r.status_code == 200
    assert "rows" in r.json()


def test_finance_report_csv():
    headers = _headers("finance@demo.com")
    r = client.get(
        "/api/v1/admin/finance-reports/outstanding?format=csv",
        headers=headers,
    )
    assert r.status_code == 200
    assert "text/csv" in r.headers.get("content-type", "")


def test_margin_by_case_includes_pct_and_low_flag():
    from app.core.billing_validation import margin_pct_and_flag
    from app.services.billing_period_snapshot_service import enrich_margin_row

    ok = margin_pct_and_flag(client_total_inr=10000, therapist_total_inr=6000)
    assert ok["marginPct"] == 40.0
    assert ok["lowMargin"] is False
    assert ok["marginFlag"] == ""

    low = margin_pct_and_flag(client_total_inr=10000, therapist_total_inr=8000)
    assert low["marginPct"] == 20.0
    assert low["lowMargin"] is True
    assert low["marginFlag"] == "LOW_MARGIN_BELOW_30"

    row = enrich_margin_row(
        {
            "caseId": 1,
            "clientTotalInr": 10000,
            "therapistTotalInr": 7500,
            "marginInr": 2500,
            "sessionCount": 4,
        }
    )
    assert row["marginPct"] == 25.0
    assert row["lowMargin"] is True
    assert "pay_share" not in row
    assert "PERCENTAGE" not in str(row)

    headers = _headers("finance@demo.com")
    r = client.get(
        "/api/v1/admin/finance-reports/margin-by-case?billing_month=2026-06",
        headers=headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert "rows" in body
    if body["rows"]:
        sample = body["rows"][0]
        assert "marginPct" in sample
        assert "lowMargin" in sample
        assert "marginFlag" in sample


def test_finance_report_catalog_lists_picker_reports():
    headers = _headers("finance@demo.com")
    r = client.get("/api/v1/admin/finance-reports/catalog", headers=headers)
    assert r.status_code == 200
    keys = [item["key"] for item in r.json()["reports"]]
    assert "therapist-payout-preview" in keys
    assert "collections" in keys
    assert "monthly-billing" in keys
    collections = next(item for item in r.json()["reports"] if item["key"] == "collections")
    assert "date_from" in collections["filters"]
    assert "status" in collections["filters"]


def test_collections_accepts_period_and_status():
    headers = _headers("superadmin@demo.com")
    r = client.get(
        "/api/v1/admin/finance-reports/collections"
        "?date_from=2026-10-01&date_to=2026-10-31&status=CONFIRMED&page=1&page_size=50",
        headers=headers,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["count"] >= len(data["rows"])
    for row in data["rows"]:
        assert row.get("paymentStatus") == "CONFIRMED"
        sample = str(row)
        assert "Therapist Share" not in sample
        assert "pay_share_pct" not in sample


def test_monthly_billing_accepts_month_case_type_and_status():
    headers = _headers("superadmin@demo.com")
    r = client.get(
        "/api/v1/admin/finance-reports/monthly-billing"
        "?billing_month=2026-10&product_module=homecare&status=PAID&page=1&page_size=50",
        headers=headers,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert "rows" in data
    for row in data["rows"]:
        assert row.get("status") == "PAID"
