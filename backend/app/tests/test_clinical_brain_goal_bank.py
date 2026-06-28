"""Clinical Brain goal bank + templates API."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.tests.conftest import api_first_case_id, login_headers

client = TestClient(app)


def test_admin_goal_bank_lists_org_items():
    headers = login_headers(client, "superadmin@demo.com")
    r = client.get("/api/v1/admin/goal-bank", headers=headers)
    assert r.status_code == 200, r.text
    items = r.json().get("items") or []
    assert isinstance(items, list)


def test_therapist_goal_templates_scoped_to_case():
    headers = login_headers(client, "therapist@demo.com")
    case_id = api_first_case_id(client, headers)
    r = client.get(f"/api/v1/cases/{case_id}/goal-templates", headers=headers)
    assert r.status_code == 200, r.text
    assert "items" in r.json()


def test_parent_cannot_access_goal_bank():
    headers = login_headers(client, "parent@demo.com")
    r = client.get("/api/v1/admin/goal-bank", headers=headers)
    assert r.status_code == 403
