"""Parent goal inputs."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _login(email: str) -> dict[str, str]:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "demo123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _parent_case_id() -> int:
    headers = _login("parent@demo.com")
    cases = client.get("/api/v1/parent/cases", headers=headers).json()
    return cases[0]["id"]


def test_parent_can_submit_goal_input():
    case_id = _parent_case_id()
    headers = _login("parent@demo.com")
    r = client.post(
        f"/api/v1/parent/cases/{case_id}/goal-inputs",
        headers=headers,
        json={
            "goal_ref": "iep-1",
            "input_type": "see_at_home",
            "comment": "We see more engagement after breakfast",
        },
    )
    assert r.status_code == 201, r.text
    assert r.json()["review_status"] == "pending"


def test_parent_cannot_submit_for_other_case():
    headers = _login("parent@demo.com")
    r = client.post(
        "/api/v1/parent/cases/99999/goal-inputs",
        headers=headers,
        json={"goal_ref": "iep-1", "input_type": "see_at_home"},
    )
    assert r.status_code in (403, 404)
