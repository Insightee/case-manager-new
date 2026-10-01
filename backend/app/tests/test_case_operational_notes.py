"""Staff-only case operational notes journal."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.seed.demo_seed import run as seed_run

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    seed_run()


def _login(email: str, password: str = "demo123") -> dict[str, str]:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _make_case(admin_headers: dict) -> int:
    suffix = uuid.uuid4().hex[:8]
    fam = client.post(
        "/api/v1/admin/families",
        headers=admin_headers,
        json={
            "parent_email": f"ops-note-{suffix}@demo.com",
            "parent_full_name": "Ops Note Parent",
            "child": {"first_name": "Ops", "last_name": suffix},
            "send_invite": False,
        },
    )
    assert fam.status_code == 201, fam.text
    child_id = fam.json()["childId"]
    created = client.post(
        "/api/v1/cases",
        headers=admin_headers,
        json={
            "child_id": child_id,
            "service_type": "Homecare",
            "product_module": "homecare",
            "billing_type": "PER_SESSION",
            "client_rate_per_session_inr": 1500,
            "compensation_mode": "PERCENTAGE",
            "pay_share_amount_inr": 50,
        },
    )
    assert created.status_code == 201, created.text
    return created.json()["id"]


def test_operational_notes_create_list_and_sync_case_notes():
    admin = _login("superadmin@demo.com")
    case_id = _make_case(admin)

    first = client.post(
        f"/api/v1/cases/{case_id}/operational-notes",
        headers=admin,
        json={"heading": "Therapist preference", "body": "Needs Hindi-speaking therapist."},
    )
    assert first.status_code == 201, first.text
    assert first.json()["author_name"]
    assert first.json()["heading"] == "Therapist preference"

    second = client.post(
        f"/api/v1/cases/{case_id}/operational-notes",
        headers=admin,
        json={"heading": "Billing flag", "body": "Finance to review package renewal."},
    )
    assert second.status_code == 201, second.text

    listed = client.get(f"/api/v1/cases/{case_id}/operational-notes", headers=admin)
    assert listed.status_code == 200
    rows = listed.json()
    assert len(rows) == 2
    assert rows[0]["heading"] == "Billing flag"
    assert rows[1]["heading"] == "Therapist preference"

    latest = client.get(f"/api/v1/cases/{case_id}/operational-notes/latest", headers=admin)
    assert latest.status_code == 200
    assert latest.json()["heading"] == "Billing flag"

    case_get = client.get(f"/api/v1/cases/{case_id}", headers=admin)
    assert case_get.status_code == 200
    assert "Billing flag" in (case_get.json().get("notes") or "")


def test_operational_note_requires_heading_and_body():
    admin = _login("superadmin@demo.com")
    case_id = _make_case(admin)
    bad = client.post(
        f"/api/v1/cases/{case_id}/operational-notes",
        headers=admin,
        json={"heading": " ", "body": "Something"},
    )
    assert bad.status_code == 422 or bad.status_code == 400


def test_only_super_admin_can_delete_operational_note():
    admin = _login("superadmin@demo.com")
    module_admin = _login("admin@demo.com")
    case_id = _make_case(admin)
    created = client.post(
        f"/api/v1/cases/{case_id}/operational-notes",
        headers=admin,
        json={"heading": "To delete", "body": "Temporary note."},
    )
    assert created.status_code == 201, created.text
    note_id = created.json()["id"]

    denied = client.delete(f"/api/v1/cases/{case_id}/operational-notes/{note_id}", headers=module_admin)
    assert denied.status_code == 403

    ok = client.delete(f"/api/v1/cases/{case_id}/operational-notes/{note_id}", headers=admin)
    assert ok.status_code == 204

    listed = client.get(f"/api/v1/cases/{case_id}/operational-notes", headers=admin)
    assert listed.json() == []


def test_parent_cannot_access_operational_notes():
    admin = _login("superadmin@demo.com")
    parent = _login("parent@demo.com")
    case_id = _make_case(admin)
    client.post(
        f"/api/v1/cases/{case_id}/operational-notes",
        headers=admin,
        json={"heading": "Internal only", "body": "Parents must not see this."},
    )
    listed = client.get(f"/api/v1/cases/{case_id}/operational-notes", headers=parent)
    assert listed.status_code in (403, 404)

    parent_cases = client.get("/api/v1/parent/cases", headers=parent).json()
    for row in parent_cases:
        assert "operational" not in str(row).lower()
        assert "Internal only" not in str(row)

