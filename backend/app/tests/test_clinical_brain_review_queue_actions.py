"""Unified clinical review queue actions."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _login(email: str) -> dict[str, str]:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "demo123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _queue_item_id(headers: dict[str, str]) -> int | None:
    client.get("/api/v1/clinical-brain/review-queue", headers=headers)
    r = client.get("/api/v1/clinical-brain/review-queue", headers=headers)
    items = r.json().get("items") or []
    return items[0]["id"] if items else None


def test_cm_can_list_unified_queue():
    headers = _login("superadmin@demo.com")
    r = client.get("/api/v1/clinical-brain/review-queue", headers=headers)
    assert r.status_code == 200
    assert "items" in r.json()


def test_therapist_cannot_act_on_queue():
    headers = _login("therapist@demo.com")
    r = client.post(
        "/api/v1/clinical-brain/review-queue/1/action",
        headers=headers,
        json={"action": "approve"},
    )
    assert r.status_code == 403


def test_reject_requires_note():
    headers = _login("superadmin@demo.com")
    item_id = _queue_item_id(headers)
    if not item_id:
        return
    r = client.post(
        f"/api/v1/clinical-brain/review-queue/{item_id}/action",
        headers=headers,
        json={"action": "reject"},
    )
    assert r.status_code == 400


def test_close_action_updates_status():
    headers = _login("superadmin@demo.com")
    item_id = _queue_item_id(headers)
    if not item_id:
        return
    r = client.post(
        f"/api/v1/clinical-brain/review-queue/{item_id}/action",
        headers=headers,
        json={"action": "close", "reviewer_note": "No action needed"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "closed"
