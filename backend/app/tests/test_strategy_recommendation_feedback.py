"""Backend tests for strategy recommendation feedback."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.database import SessionLocal
from app.main import app
from app.models.case import Case
from app.models.goal_repository import StrategyRepositoryItem, RepositoryItemStatus
from app.models.user import User

client = TestClient(app)


def _login(email: str) -> dict[str, str]:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "demo123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _therapist_case_id() -> int:
    headers = _login("therapist@demo.com")
    cases = client.get("/api/v1/cases?assigned=true&page_size=1", headers=headers).json()
    return cases["items"][0]["id"]


def test_therapist_can_submit_feedback_for_assigned_case():
    case_id = _therapist_case_id()
    headers = _login("therapist@demo.com")
    with SessionLocal() as db:
        strat = db.scalars(select(StrategyRepositoryItem).limit(1)).first()
        assert strat
        sid = strat.id
    r = client.post(
        f"/api/v1/clinical-brain/cases/{case_id}/strategy-recommendation-feedback",
        headers=headers,
        json={
            "strategy_repository_item_id": sid,
            "feedback_status": "accepted",
            "recommendation_source": "library_match",
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["feedback_status"] == "accepted"


def test_adaptation_text_saved():
    case_id = _therapist_case_id()
    headers = _login("therapist@demo.com")
    r = client.post(
        f"/api/v1/clinical-brain/cases/{case_id}/strategy-recommendation-feedback",
        headers=headers,
        json={
            "feedback_status": "adapted",
            "adaptation_text": "Used visual cue before transition",
        },
    )
    assert r.status_code == 200, r.text
    assert "visual cue" in (r.json().get("adaptation_text") or "")


def test_invalid_feedback_status_returns_400():
    case_id = _therapist_case_id()
    headers = _login("therapist@demo.com")
    r = client.post(
        f"/api/v1/clinical-brain/cases/{case_id}/strategy-recommendation-feedback",
        headers=headers,
        json={"feedback_status": "invalid_status"},
    )
    assert r.status_code == 400


def test_parent_cannot_submit_feedback():
    case_id = _therapist_case_id()
    headers = _login("parent@demo.com")
    r = client.post(
        f"/api/v1/clinical-brain/cases/{case_id}/strategy-recommendation-feedback",
        headers=headers,
        json={"feedback_status": "accepted"},
    )
    assert r.status_code in (403, 404)


def test_cm_can_list_feedback():
    case_id = _therapist_case_id()
    admin = _login("superadmin@demo.com")
    r = client.get(
        f"/api/v1/clinical-brain/cases/{case_id}/strategy-recommendation-feedback",
        headers=admin,
    )
    assert r.status_code == 200
    assert "items" in r.json()


def test_list_feedback_filters_by_goal_card_id():
    case_id = _therapist_case_id()
    headers = _login("therapist@demo.com")
    client.post(
        f"/api/v1/clinical-brain/cases/{case_id}/strategy-recommendation-feedback",
        headers=headers,
        json={"feedback_status": "accepted", "goal_card_id": 424242},
    )
    r = client.get(
        f"/api/v1/clinical-brain/cases/{case_id}/strategy-recommendation-feedback?goal_card_id=424242",
        headers=headers,
    )
    assert r.status_code == 200
    assert any(i.get("goal_card_id") == 424242 for i in r.json()["items"])


def test_needs_cm_input_creates_queue_item():
    case_id = _therapist_case_id()
    headers = _login("therapist@demo.com")
    client.post(
        f"/api/v1/clinical-brain/cases/{case_id}/strategy-recommendation-feedback",
        headers=headers,
        json={"feedback_status": "needs_cm_input", "dismissal_reason": "Unsure about fit"},
    )
    admin = _login("superadmin@demo.com")
    q = client.get("/api/v1/clinical-brain/review-queue?item_type=recommendation_feedback", headers=admin)
    assert q.status_code == 200
    types = [i.get("item_type") for i in q.json().get("items", [])]
    assert "recommendation_feedback" in types
