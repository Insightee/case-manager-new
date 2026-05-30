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
