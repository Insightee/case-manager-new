"""Clinical review queue admin API."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.tests.conftest import login_headers

client = TestClient(app)


def test_clinical_review_queue_goal_tab():
    headers = login_headers(client, "superadmin@demo.com")
    r = client.get("/api/v1/admin/clinical-review-queue?tab=goal_candidates", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "pending_goals" in body
    assert "pending_strategies" in body


def test_therapist_cannot_access_review_queue():
    headers = login_headers(client, "therapist@demo.com")
    r = client.get("/api/v1/admin/clinical-review-queue", headers=headers)
    assert r.status_code == 403
