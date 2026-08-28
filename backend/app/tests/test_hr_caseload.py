"""HR caseload endpoint smoke tests."""
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


def test_hr_caseload_includes_identity_and_pay_for_hr():
    res = client.get("/api/v1/hr/caseload", headers=_auth_headers("hr@demo.com"))
    assert res.status_code == 200, res.text
    data = res.json()
    assert "cases" in data and "therapists" in data and "summary" in data
    assert data.get("include_pay") is True
    if data["cases"]:
        row = data["cases"][0]
        assert "case_code" in row
        assert "child_name" in row
        assert "status" in row


def test_hr_caseload_superadmin_ok():
    res = client.get("/api/v1/hr/caseload", headers=_auth_headers("superadmin@demo.com"))
    assert res.status_code == 200, res.text
    assert res.json().get("include_pay") is True


def test_hr_caseload_forbidden_for_therapist():
    res = client.get("/api/v1/hr/caseload", headers=_auth_headers("therapist@demo.com"))
    assert res.status_code == 403
