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


def test_resolve_requires_message():
    admin = _login("superadmin@demo.com")
    created = client.post(
        "/api/v1/tickets",
        headers=_headers(admin),
        json={"subject": "Note required", "body": "Test", "category": "OTHER"},
    )
    ticket_id = created.json()["id"]
    empty = client.post(
        f"/api/v1/tickets/{ticket_id}/resolve",
        headers=_headers(admin),
        json={"note": "  "},
    )
    assert empty.status_code == 400


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


def test_parent_resolve_feedback_reopen_and_close():
    parent = _login("parent@demo.com")
    admin = _login("superadmin@demo.com")

    cases = client.get("/api/v1/parent/cases", headers=_headers(parent)).json()
    case_id = cases[0]["id"] if cases else None
    created = client.post(
        "/api/v1/parent/support-requests",
        headers=_headers(parent),
        json={
            "subject": "Billing question",
            "message": "Invoice mismatch",
            "topic": "BILLING",
            "case_id": case_id,
        },
    )
    assert created.status_code == 201
    ticket_id = created.json()["id"]

    client.post(
        f"/api/v1/tickets/{ticket_id}/messages",
        headers=_headers(admin),
        json={"body": "We adjusted the invoice."},
    )
    client.post(
        f"/api/v1/tickets/{ticket_id}/resolve",
        headers=_headers(admin),
        json={"note": "Credit applied"},
    )

    detail = client.get(f"/api/v1/parent/support/tickets/{ticket_id}", headers=_headers(parent))
    assert detail.status_code == 200
    assert detail.json()["can_accept"] is True

    no_rating = client.post(
        f"/api/v1/parent/support/tickets/{ticket_id}/accept",
        headers=_headers(parent),
        json={"feedback": "Looks good"},
    )
    assert no_rating.status_code == 400

    reopened = client.post(
        f"/api/v1/parent/support/tickets/{ticket_id}/reopen",
        headers=_headers(parent),
        json={"note": "Still seeing wrong amount"},
    )
    assert reopened.status_code == 200
    assert reopened.json()["status"] == "IN_PROGRESS"
    bodies = [m["body"] for m in reopened.json()["messages"]]
    assert any("[Reopened]" in b for b in bodies)

    client.post(
        f"/api/v1/tickets/{ticket_id}/resolve",
        headers=_headers(admin),
        json={"note": "Fixed again"},
    )

    closed = client.post(
        f"/api/v1/parent/support/tickets/{ticket_id}/accept",
        headers=_headers(parent),
        json={"rating": 5, "feedback": "All sorted now"},
    )
    assert closed.status_code == 200
    assert closed.json()["status"] == "CLOSED"
    assert closed.json()["parent_satisfaction_rating"] == 5
