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
    assert data["scope"] == "finance_desk"
    assert data["tabs"]["tickets"] is True
    assert data["tabs"]["incidents"] is True
    assert data["tabs"]["history"] is True
    assert data["can_manage_incidents"] is False


def test_support_capabilities_hr_all_tabs():
    r = client.get("/api/v1/admin/support/capabilities", headers=_auth_headers("hr@demo.com"))
    assert r.status_code == 200
    data = r.json()
    assert data["scope"] == "hr_desk"
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


def test_support_capabilities_case_manager_team_scope():
    r = client.get("/api/v1/admin/support/capabilities", headers=_auth_headers("casemanager@demo.com"))
    assert r.status_code == 200
    data = r.json()
    assert data["scope"] == "team"
    assert data["tabs"]["tickets"] is True
    assert data["tabs"]["incidents"] is True


def test_case_manager_ticket_list_subset_of_superadmin():
    admin = client.get("/api/v1/tickets?page_size=100", headers=_auth_headers("superadmin@demo.com"))
    cm = client.get("/api/v1/tickets?page_size=100", headers=_auth_headers("casemanager@demo.com"))
    assert admin.status_code == 200
    assert cm.status_code == 200
    admin_ids = {row["id"] for row in admin.json().get("items") or []}
    cm_ids = {row["id"] for row in cm.json().get("items") or []}
    assert cm_ids.issubset(admin_ids)
    assert len(cm_ids) <= len(admin_ids)


def test_case_manager_incident_list_subset_of_superadmin():
    admin = client.get("/api/v1/incidents?page_size=100", headers=_auth_headers("superadmin@demo.com"))
    cm = client.get("/api/v1/incidents?page_size=100", headers=_auth_headers("casemanager@demo.com"))
    assert admin.status_code == 200
    assert cm.status_code == 200
    admin_ids = {row["id"] for row in admin.json().get("items") or []}
    cm_ids = {row["id"] for row in cm.json().get("items") or []}
    assert cm_ids.issubset(admin_ids)
    assert len(cm_ids) <= len(admin_ids)


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


def test_finance_desk_sees_finance_category_tickets():
    therapist = _auth_headers("therapist@demo.com")
    finance = _auth_headers("finance@demo.com")
    admin = _auth_headers("superadmin@demo.com")

    created = client.post(
        "/api/v1/tickets",
        headers=therapist,
        json={
            "subject": "Finance desk routing test",
            "body": "Need invoice correction",
            "category": "FINANCE",
        },
    )
    assert created.status_code == 201
    ticket_id = created.json()["id"]

    detail = client.get(f"/api/v1/tickets/{ticket_id}", headers=finance)
    assert detail.status_code == 200
    body = detail.json()
    assert body["category"] == "FINANCE"
    assert body["topic"] == "BILLING_PAYMENT"
    assert body["assigned_to_name"] == "Finance User"

    finance_list = client.get("/api/v1/tickets?page_size=100", headers=finance)
    assert finance_list.status_code == 200
    finance_ids = {row["id"] for row in finance_list.json().get("items") or []}
    assert ticket_id in finance_ids

    other = client.post(
        "/api/v1/tickets",
        headers=therapist,
        json={"subject": "General other ticket", "body": "Unrelated", "category": "OTHER"},
    )
    assert other.status_code == 201
    other_id = other.json()["id"]

    finance_list_after = client.get("/api/v1/tickets?page_size=100", headers=finance)
    finance_ids_after = {row["id"] for row in finance_list_after.json().get("items") or []}
    assert ticket_id in finance_ids_after
    assert other_id not in finance_ids_after

    admin_list = client.get("/api/v1/tickets?page_size=100", headers=admin)
    admin_ids = {row["id"] for row in admin_list.json().get("items") or []}
    assert ticket_id in admin_ids
    assert other_id in admin_ids
