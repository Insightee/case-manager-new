"""Parent therapist chat thread (support ticket backend)."""

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.database import SessionLocal
from app.main import app
from app.models.support_ticket import SupportTicket
from app.services.parent_therapist_chat_service import THERAPIST_CHAT_SUBJECT

client = TestClient(app)


def _login(email: str, password: str = "demo123") -> dict:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _chat_ticket_count(parent_user_id: int, case_id: int) -> int:
    with SessionLocal() as db:
        return int(
            db.scalar(
                select(func.count())
                .select_from(SupportTicket)
                .where(
                    SupportTicket.raised_by_user_id == parent_user_id,
                    SupportTicket.case_id == case_id,
                    SupportTicket.subject == THERAPIST_CHAT_SUBJECT,
                )
            )
            or 0
        )


def test_parent_therapist_chat_get_does_not_create_ticket():
    headers = _login("parent@demo.com")
    cases = client.get("/api/v1/parent/cases", headers=headers).json()
    if not cases:
        return
    case_id = cases[0]["id"]
    parent_id = client.get("/api/v1/auth/me", headers=headers).json()["id"]
    before = _chat_ticket_count(parent_id, case_id)

    r1 = client.get(f"/api/v1/parent/therapist-chat?case_id={case_id}", headers=headers)
    assert r1.status_code == 200, r1.text
    assert r1.json() is None

    r2 = client.get(f"/api/v1/parent/therapist-chat?case_id={case_id}", headers=headers)
    assert r2.status_code == 200
    assert r2.json() is None
    assert _chat_ticket_count(parent_id, case_id) == before


def test_parent_therapist_chat_starts_on_first_message():
    headers = _login("parent@demo.com")
    cases = client.get("/api/v1/parent/cases", headers=headers).json()
    if not cases:
        return
    case_id = cases[0]["id"]

    created = client.post(
        "/api/v1/parent/therapist-chat",
        headers=headers,
        json={"case_id": case_id, "message": "Hello therapist"},
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["subject"] == "Therapist chat"
    assert body["topic"] == "OTHER"
    assert body.get("assigned_to_name")

    r2 = client.get(f"/api/v1/parent/therapist-chat?case_id={case_id}", headers=headers)
    assert r2.status_code == 200
    assert r2.json()["id"] == body["id"]
