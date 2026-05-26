from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.models.incident import Incident
from app.models.user import User
from app.seed.demo_seed import run as seed_run
from app.services.ticket_escalation_service import resolve_users_for_role_tag

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    seed_run()


def test_admin_tag_resolves_module_admin():
    from app.core.database import SessionLocal

    db = SessionLocal()
    try:
        module_admins = db.scalars(
            select(User).where(User.email.in_(["moduleadmin@demo.com", "superadmin@demo.com"]))
        ).all()
        ids = resolve_users_for_role_tag(db, "ADMIN", None)
        for u in module_admins:
            if u.is_active and "MODULE_ADMIN" in u.role_names or "SUPER_ADMIN" in u.role_names:
                assert u.id in ids
    finally:
        db.close()


@patch("app.services.incident_notify_service.notify_incident_tagged")
def test_patch_tagged_user_ids_notifies(mock_notify):
    login = client.post("/api/v1/auth/login", json={"email": "superadmin@demo.com", "password": "demo123"})
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    listed = client.get("/api/v1/incidents?page_size=1", headers=headers)
    assert listed.status_code == 200
    items = listed.json().get("items") or listed.json()
    if isinstance(items, dict):
        items = items.get("items", [])
    if not items:
        pytest.skip("No incidents in seed data")
    inc_id = items[0]["id"]

    users_resp = client.get("/api/v1/admin/users?page_size=100", headers=headers).json()
    all_users = users_resp.get("items") if isinstance(users_resp, dict) else users_resp
    finance_users = [u for u in all_users if "FINANCE" in (u.get("roles") or [])]
    if not finance_users:
        pytest.skip("No finance user in seed")
    tag_id = finance_users[0]["id"]

    r = client.patch(
        f"/api/v1/incidents/{inc_id}",
        headers=headers,
        json={"tagged_user_ids": [tag_id], "tagged_roles": ["ADMIN"]},
    )
    assert r.status_code == 200
    body = r.json()
    assert tag_id in body.get("tagged_user_ids", [])
    mock_notify.assert_called_once()

    detail = client.get(f"/api/v1/incidents/{inc_id}", headers=headers)
    assert detail.status_code == 200
    assert any(t["id"] == tag_id for t in detail.json().get("tagged_users", []))
