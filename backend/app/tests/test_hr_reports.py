from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.seed.demo_seed import run as seed_run

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    seed_run()


def _auth_headers(email: str = "hr@demo.com"):
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "demo123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_hr_staff_status_report():
    r = client.get("/api/v1/admin/hr-reports/staff-status", headers=_auth_headers())
    assert r.status_code == 200
    data = r.json()
    assert data["count"] >= 1
    assert "email" in data["rows"][0]


def test_hr_therapist_status_report():
    r = client.get("/api/v1/admin/hr-reports/therapist-status", headers=_auth_headers())
    assert r.status_code == 200
    assert r.json()["count"] >= 0


def test_hr_home_landing_route():
    r = client.get("/api/v1/admin/home", headers=_auth_headers())
    assert r.status_code == 200
    data = r.json()
    assert data["landing_route"] == "/admin"
    assert data["dashboard_variant"] == "hr"


def test_finance_cannot_export_hr_reports():
    fin = client.post("/api/v1/auth/login", json={"email": "finance@demo.com", "password": "demo123"})
    headers = {"Authorization": f"Bearer {fin.json()['access_token']}"}
    r = client.get("/api/v1/admin/hr-reports/staff-status", headers=headers)
    assert r.status_code == 403
