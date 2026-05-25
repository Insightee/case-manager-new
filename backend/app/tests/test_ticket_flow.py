from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.support_ticket import SupportTicket, TicketMessage, TicketStatus
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


def test_therapist_ticket_reply_and_escalate_after_staff_message():
    therapist = _login("therapist@demo.com")
    admin = _login("superadmin@demo.com")

    created = client.post(
        "/api/v1/tickets",
        headers=_headers(therapist),
        json={"subject": "Flow test", "body": "Need help with schedule", "category": "OTHER"},
    )
    assert created.status_code == 201
    ticket_id = created.json()["id"]

    esc_before = client.post(
        f"/api/v1/tickets/{ticket_id}/escalate",
        headers=_headers(therapist),
        json={"reason": "Too early"},
    )
    assert esc_before.status_code == 400

    client.post(
        f"/api/v1/tickets/{ticket_id}/messages",
        headers=_headers(admin),
        json={"body": "We are looking into this."},
    )

    detail = client.get(f"/api/v1/tickets/{ticket_id}", headers=_headers(therapist))
    assert detail.status_code == 200
    assert detail.json()["can_escalate"] is True
    assert len(detail.json()["messages"]) >= 2

    esc = client.post(
        f"/api/v1/tickets/{ticket_id}/escalate",
        headers=_headers(therapist),
        json={"reason": "Need supervisor"},
    )
    assert esc.status_code == 200
    assert esc.json()["escalation_level"] >= 1


def test_staff_resolve_and_raiser_close():
    therapist = _login("therapist@demo.com")
    admin = _login("superadmin@demo.com")

    created = client.post(
        "/api/v1/tickets",
        headers=_headers(therapist),
        json={"subject": "Resolve flow", "body": "Billing question", "category": "FINANCE"},
    )
    ticket_id = created.json()["id"]

    client.post(
        f"/api/v1/tickets/{ticket_id}/messages",
        headers=_headers(admin),
        json={"body": "Applied credit to your account."},
    )

    resolved = client.post(
        f"/api/v1/tickets/{ticket_id}/resolve",
        headers=_headers(admin),
        json={"note": "Credit applied"},
    )
    assert resolved.status_code == 200
    assert resolved.json()["status"] == "RESOLVED"

    closed = client.post(
        f"/api/v1/tickets/{ticket_id}/close",
        headers=_headers(therapist),
        json={"accept_resolution": True, "note": "Thanks"},
    )
    assert closed.status_code == 200
    assert closed.json()["status"] == "CLOSED"
