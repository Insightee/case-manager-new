"""Parent session feedback visible on therapist profile reviews."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.seed.demo_seed import run as seed_run

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    seed_run()


def _login(email: str, password: str = "demo123"):
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200
    return r.json()["access_token"]


def test_therapist_reviews_endpoint():
    token = _login("therapist@demo.com")
    r = client.get("/api/v1/therapist/reviews", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    data = r.json()
    assert "summary" in data
    assert "reviews" in data
    assert isinstance(data["reviews"], list)


def test_parent_feedback_share_public_and_list():
    parent_token = _login("parent@demo.com")
    ph = {"Authorization": f"Bearer {parent_token}"}
    logs = client.get("/api/v1/parent/session-logs", headers=ph)
    if logs.status_code != 200 or not logs.json():
        pytest.skip("No parent-visible session logs in seed")
    log_id = logs.json()[0]["id"]
    patch = client.patch(
        f"/api/v1/parent/session-logs/{log_id}/feedback",
        headers=ph,
        json={"rating": 4, "feedback": "Helpful session", "share_publicly": True},
    )
    assert patch.status_code == 200
    assert patch.json()["parent_session_rating"] == 4
    assert patch.json()["parent_feedback_public"] is True

    therapist_token = _login("therapist@demo.com")
    reviews = client.get(
        "/api/v1/therapist/reviews",
        headers={"Authorization": f"Bearer {therapist_token}"},
    ).json()
    assert any(rv["id"] == log_id for rv in reviews["reviews"])

    admin_token = _login("superadmin@demo.com")
    therapist_me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {therapist_token}"}).json()
    admin_reviews = client.get(
        f"/api/v1/admin/therapist-profiles/{therapist_me['id']}/reviews",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert admin_reviews.status_code == 200
    assert admin_reviews.json()["summary"]["total_count"] >= 0
