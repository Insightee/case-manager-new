"""Insights Ask API — case-scoped chat on explicit send only."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.database import SessionLocal, ensure_sqlite_schema_patches
from app.main import app
from app.models.ai_generation import AiGenerationLog
from app.models.case import Case
from app.models.user import User
from app.services.insights import insights_chat_usage_limiter as ask_limiter

ensure_sqlite_schema_patches()
client = TestClient(app)


def _login(email: str, password: str = "demo123") -> dict:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _therapist_case_id() -> int:
    with SessionLocal() as db:
        case = db.scalars(select(Case).limit(1)).first()
        assert case
        return case.id


def test_ask_requires_question():
    headers = _login("therapist@demo.com")
    case_id = _therapist_case_id()
    r = client.post(
        f"/api/v1/cases/{case_id}/insights/ask",
        headers=headers,
        json={"question": "   "},
    )
    assert r.status_code == 400
    assert "question" in r.json()["detail"].lower()


def test_ask_returns_mock_answer_without_tab_open_ai():
    headers = _login("therapist@demo.com")
    case_id = _therapist_case_id()
    r = client.post(
        f"/api/v1/cases/{case_id}/insights/ask",
        headers=headers,
        json={"question": "What should I focus on next session?"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("answer")
    assert body.get("capExceeded") is False
    assert body["usage"]["remaining"] <= ask_limiter.WEEKLY_ASK_CAP - 1


def test_ask_respects_weekly_cap():
    headers = _login("therapist@demo.com")
    case_id = _therapist_case_id()
    with SessionLocal() as db:
        therapist = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
        assert therapist
        for _ in range(ask_limiter.WEEKLY_ASK_CAP):
            db.add(
                AiGenerationLog(
                    user_id=therapist.id,
                    case_id=case_id,
                    action=ask_limiter.INSIGHTS_ASK_ACTION,
                    provider="mock",
                    input_hash="cap-test",
                )
            )
        db.commit()

    r = client.post(
        f"/api/v1/cases/{case_id}/insights/ask",
        headers=headers,
        json={"question": "One more question"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("capExceeded") is True
    assert body.get("answer") is None
    assert "ask limit" in (body.get("message") or "").lower()
