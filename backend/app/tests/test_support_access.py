from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.seed.demo_seed import run as seed_run

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    seed_run()


def _auth_headers(email: str = "superadmin@demo.com"):
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "demo123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_support_capabilities_superadmin_full():
    r = client.get("/api/v1/admin/support/capabilities", headers=_auth_headers())
    assert r.status_code == 200
    data = r.json()
    assert data["scope"] == "full"
    assert data["tabs"]["tickets"] is True
    assert data["tabs"]["incidents"] is True
    assert data["tabs"]["history"] is True
    assert data["can_manage_incidents"] is True


def test_support_capabilities_finance_all_tabs():
    r = client.get("/api/v1/admin/support/capabilities", headers=_auth_headers("finance@demo.com"))
    assert r.status_code == 200
    data = r.json()
    assert data["scope"] == "full"
    assert data["tabs"]["tickets"] is True
    assert data["tabs"]["incidents"] is True
    assert data["tabs"]["history"] is True
    assert data["can_manage_incidents"] is False


def test_support_capabilities_hr_all_tabs():
    r = client.get("/api/v1/admin/support/capabilities", headers=_auth_headers("hr@demo.com"))
    assert r.status_code == 200
    data = r.json()
    assert data["scope"] == "full"
    assert data["tabs"]["tickets"] is True
    assert data["tabs"]["incidents"] is True
    assert data["tabs"]["history"] is True
    assert data["can_manage_incidents"] is False


def test_finance_history_includes_incidents_when_seeded():
    r = client.get(
        "/api/v1/admin/support/history?record_type=incidents&page_size=50",
        headers=_auth_headers("finance@demo.com"),
    )
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) >= 1
    assert all(row["record_type"] == "incident" for row in items)


def test_finance_history_includes_demo_tickets():
    r = client.get(
        "/api/v1/admin/support/history?record_type=tickets&page_size=50",
        headers=_auth_headers("finance@demo.com"),
    )
    assert r.status_code == 200
    items = r.json()["items"]
    assert any("finance" in (row.get("subject") or "").lower() for row in items)


def test_finance_can_list_incidents():
    r = client.get("/api/v1/incidents?page_size=20", headers=_auth_headers("finance@demo.com"))
    assert r.status_code == 200
    items = r.json().get("items") or []
    assert len(items) >= 1


def test_support_capabilities_admin_full():
    r = client.get("/api/v1/admin/support/capabilities", headers=_auth_headers("admin@demo.com"))
    assert r.status_code == 200
    data = r.json()
    assert data["tabs"]["tickets"] is True
    assert data["tabs"]["incidents"] is True
    assert data["tabs"]["history"] is True


def test_therapist_no_admin_support_capabilities():
    r = client.get("/api/v1/admin/support/capabilities", headers=_auth_headers("therapist@demo.com"))
    assert r.status_code == 200
    data = r.json()
    assert data["scope"] == "none"
    assert data["tabs"]["history"] is False
