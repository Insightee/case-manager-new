from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _login(email: str, password: str = "demo123"):
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200
    return r.json()["access_token"]


def _complete_session_with_log(headers):
    upcoming = client.get("/api/v1/sessions/upcoming", headers=headers).json()
    if not upcoming:
        pytest.skip("No scheduled sessions")
    sid = upcoming[0]["id"]
    client.post(f"/api/v1/sessions/{sid}/start", headers=headers)
    client.post(f"/api/v1/sessions/{sid}/end", headers=headers)
    payload = {
        "session_id": sid,
        "attendance_status": "PRESENT",
        "activities_done": "Initial activities note",
    }
    # Seeded sessions may be before today (IST); late logs require a reason on CI runners.
    created = client.post("/api/v1/daily-logs", headers=headers, json=payload)
    if created.status_code == 400 and "Late reason" in created.text:
        payload["late_reason"] = "Test log for edit-window coverage"
        created = client.post("/api/v1/daily-logs", headers=headers, json=payload)
    assert created.status_code == 201, created.text
    return created.json()


def test_log_can_edit_within_24_hours():
    token = _login("therapist@demo.com")
    headers = {"Authorization": f"Bearer {token}"}
    log = _complete_session_with_log(headers)
    assert log.get("can_edit") is True
    assert log.get("editable_until") is not None

    updated = client.patch(
        f"/api/v1/daily-logs/{log['id']}",
        headers=headers,
        json={"activities_done": "Updated within window"},
    )
    assert updated.status_code == 200
    assert updated.json()["activities_done"] == "Updated within window"


def test_log_cannot_edit_after_24_hours(monkeypatch):
    from app.models.daily_log import DailyLog
    from app.services import log_service

    token = _login("therapist@demo.com")
    headers = {"Authorization": f"Bearer {token}"}
    log = _complete_session_with_log(headers)

    original_until = log_service.log_editable_until

    def expired(_log: DailyLog):
        return datetime.now(timezone.utc) - timedelta(hours=1)

    monkeypatch.setattr(log_service, "log_editable_until", expired)

    blocked = client.patch(
        f"/api/v1/daily-logs/{log['id']}",
        headers=headers,
        json={"activities_done": "Too late"},
    )
    assert blocked.status_code == 400
    assert "24 hours" in blocked.json()["detail"]

    monkeypatch.setattr(log_service, "log_editable_until", original_until)
