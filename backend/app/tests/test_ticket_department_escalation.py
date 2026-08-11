"""Department queue escalation for support tickets."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.user import User
from app.seed.demo_seed import run as seed_run

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    seed_run()


def _login(email: str) -> str:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "demo123"})
    assert r.status_code == 200
    return r.json()["access_token"]


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_escalation_targets_lists_departments():
    admin = _login("superadmin@demo.com")
    r = client.get("/api/v1/tickets/escalation-targets", headers=_headers(admin))
    assert r.status_code == 200
    body = r.json()
    assert len(body["departments"]) >= 10
    assert isinstance(body["staff"], list)


def test_staff_escalate_to_department_queue_and_pick_up():
    from app.core.database import SessionLocal

    admin = _login("superadmin@demo.com")

    with SessionLocal() as db:
        admin_user = db.query(User).filter(User.email == "superadmin@demo.com").first()
        assert admin_user is not None
        admin_user.department = "OPERATIONS"
        db.commit()

    created = client.post(
        "/api/v1/tickets",
        headers=_headers(admin),
        json={"subject": "Dept queue test", "body": "Need ops review", "category": "OTHER"},
    )
    assert created.status_code == 201
    ticket_id = created.json()["id"]

    esc = client.post(
        f"/api/v1/tickets/{ticket_id}/escalate",
        headers=_headers(admin),
        json={"escalate_to_department": "OPERATIONS"},
    )
    assert esc.status_code == 200, esc.text
    detail = esc.json()
    assert detail["escalated_to_department"] == "OPERATIONS"
    assert detail["escalated_to_department_label"] == "Operations"
    assert detail["assigned_to_user_id"] is None
    assert detail["can_pick_up"] is True

    picked = client.post(f"/api/v1/tickets/{ticket_id}/pick-up", headers=_headers(admin))
    assert picked.status_code == 200
    after = picked.json()
    assert after["escalated_to_department"] is None
    assert after["assigned_to_user_id"] is not None


def test_staff_escalate_to_individual():
    admin = _login("superadmin@demo.com")
    created = client.post(
        "/api/v1/tickets",
        headers=_headers(admin),
        json={"subject": "Direct escalate", "body": "Assign to finance", "category": "FINANCE"},
    )
    ticket_id = created.json()["id"]
    targets = client.get("/api/v1/tickets/escalation-targets", headers=_headers(admin)).json()
    finance_staff = next((u for u in targets["staff"] if "FINANCE" in (u.get("roles") or [])), None)
    if not finance_staff:
        pytest.skip("No finance staff in escalation targets")
    esc = client.post(
        f"/api/v1/tickets/{ticket_id}/escalate",
        headers=_headers(admin),
        json={"assign_to_user_id": finance_staff["id"]},
    )
    assert esc.status_code == 200
    assert esc.json()["assigned_to_user_id"] == finance_staff["id"]
    assert esc.json().get("escalated_to_department") is None
