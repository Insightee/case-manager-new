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
    assert data["tabs"]["memos"] is True
    assert data["memos_mode"] == "manage"
    assert data["can_manage_incidents"] is False


def test_support_capabilities_hr_all_tabs():
    r = client.get("/api/v1/admin/support/capabilities", headers=_auth_headers("hr@demo.com"))
    assert r.status_code == 200
    data = r.json()
    assert data["scope"] == "hr_desk"
    assert data["tabs"]["tickets"] is True
    assert data["tabs"]["incidents"] is True
    assert data["tabs"]["history"] is True
    assert data["tabs"]["memos"] is True
    assert data["memos_mode"] == "manage"
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
    assert data["tabs"]["memos"] is True
    assert data["memos_mode"] == "received"


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
    assert body["assigned_to_name"] == "Chandra Kiran"

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


def test_hr_category_alternates_named_assignees():
    therapist = _auth_headers("therapist@demo.com")
    hr = _auth_headers("hr@demo.com")

    first = client.post(
        "/api/v1/tickets",
        headers=therapist,
        json={"subject": "HR routing A", "body": "Leave question", "category": "HR"},
    )
    second = client.post(
        "/api/v1/tickets",
        headers=therapist,
        json={"subject": "HR routing B", "body": "Policy question", "category": "HR"},
    )
    assert first.status_code == 201
    assert second.status_code == 201

    d1 = client.get(f"/api/v1/tickets/{first.json()['id']}", headers=hr)
    d2 = client.get(f"/api/v1/tickets/{second.json()['id']}", headers=hr)
    assert d1.status_code == 200
    assert d2.status_code == 200
    names = {d1.json()["assigned_to_name"], d2.json()["assigned_to_name"]}
    assert names == {"Sriparna Paul", "Pragya Dwivedi"}


def test_admin_desk_sees_general_not_finance():
    therapist = _auth_headers("therapist@demo.com")
    module_admin = _auth_headers("admin@demo.com")

    finance_ticket = client.post(
        "/api/v1/tickets",
        headers=therapist,
        json={"subject": "Billing only", "body": "Invoice", "category": "FINANCE"},
    )
    general_ticket = client.post(
        "/api/v1/tickets",
        headers=therapist,
        json={"subject": "General admin queue", "body": "Other issue", "category": "OTHER"},
    )
    assert finance_ticket.status_code == 201
    assert general_ticket.status_code == 201

    cap = client.get("/api/v1/admin/support/capabilities", headers=module_admin)
    assert cap.json()["scope"] == "admin_desk"

    listing = client.get("/api/v1/tickets?page_size=100", headers=module_admin)
    ids = {row["id"] for row in listing.json().get("items") or []}
    assert general_ticket.json()["id"] in ids
    assert finance_ticket.json()["id"] not in ids


def test_finance_can_resolve_and_close_homecare_billing_ticket():
    """Finance desk write must not require clinical programme module access."""
    therapist = _auth_headers("therapist@demo.com")
    finance = _auth_headers("finance@demo.com")

    created = client.post(
        "/api/v1/tickets",
        headers=therapist,
        json={
            "subject": "Invoice correction on homecare case",
            "body": "Rate mismatch on last session block",
            "category": "FINANCE",
            "product_module": "homecare",
        },
    )
    assert created.status_code == 201
    ticket_id = created.json()["id"]

    detail = client.get(f"/api/v1/tickets/{ticket_id}", headers=finance)
    assert detail.status_code == 200
    body = detail.json()
    assert body["can_close_staff"] is True
    assert body["can_resolve"] is True

    resolved = client.post(
        f"/api/v1/tickets/{ticket_id}/resolve",
        headers=finance,
        json={"note": "Applied corrected rate to the ledger."},
    )
    assert resolved.status_code == 200, resolved.text
    assert resolved.json()["status"] == "RESOLVED"

    closed = client.post(
        f"/api/v1/tickets/{ticket_id}/close",
        headers=finance,
        json={"note": "Closing after ledger correction confirmed."},
    )
    assert closed.status_code == 200, closed.text
    assert closed.json()["status"] == "CLOSED"


def test_hr_can_resolve_hr_category_ticket():
    therapist = _auth_headers("therapist@demo.com")
    hr = _auth_headers("hr@demo.com")

    created = client.post(
        "/api/v1/tickets",
        headers=therapist,
        json={
            "subject": "Leave balance question",
            "body": "Need clarification on carry-forward",
            "category": "HR",
            "product_module": "homecare",
        },
    )
    assert created.status_code == 201
    ticket_id = created.json()["id"]

    detail = client.get(f"/api/v1/tickets/{ticket_id}", headers=hr)
    assert detail.status_code == 200
    assert detail.json()["can_resolve"] is True

    resolved = client.post(
        f"/api/v1/tickets/{ticket_id}/resolve",
        headers=hr,
        json={"note": "Leave balance updated in HR records."},
    )
    assert resolved.status_code == 200, resolved.text
    assert resolved.json()["status"] == "RESOLVED"


def test_case_manager_lists_received_memo():
    hr = _auth_headers("hr@demo.com")
    cm = _auth_headers("casemanager@demo.com")

    recipients = client.get("/api/v1/memos/recipients", headers=hr)
    assert recipients.status_code == 200
    cm_user = next(r for r in recipients.json() if r["email"] == "casemanager@demo.com")

    issued = client.post(
        "/api/v1/memos",
        headers=hr,
        json={
            "category": "Performance",
            "priority": "Medium",
            "recipient_type": "Case Manager",
            "recipient_ids": [cm_user["id"]],
            "subject": "CM caseload review memo",
            "details": "Please confirm weekly review notes are up to date.",
            "reply_required": True,
            "acknowledgement_only": False,
        },
    )
    assert issued.status_code == 201, issued.text

    cap = client.get("/api/v1/admin/support/capabilities", headers=cm)
    assert cap.json()["tabs"]["memos"] is True
    assert cap.json()["memos_mode"] == "received"

    listing = client.get("/api/v1/memos", headers=cm)
    assert listing.status_code == 200
    subjects = [m["subject"] for m in listing.json()]
    assert "CM caseload review memo" in subjects
