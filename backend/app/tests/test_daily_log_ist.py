from __future__ import annotations

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app.core.timezone import today_ist
from app.main import app
from app.seed.demo_seed import run as seed_run

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    seed_run()


def _login(email: str = "therapist@demo.com") -> str:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "demo123"})
    assert r.status_code == 200
    return r.json()["access_token"]


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _end_upcoming_session(headers) -> dict:
    upcoming = client.get("/api/v1/sessions/upcoming", headers=headers).json()
    if not upcoming:
        pytest.skip("No scheduled sessions")
    sid = upcoming[0]["id"]
    client.post(f"/api/v1/sessions/{sid}/start", headers=headers)
    end = client.post(f"/api/v1/sessions/{sid}/end", headers=headers)
    assert end.status_code == 200
    return end.json()


def test_create_log_requires_late_reason_for_past_scheduled_date():
    token = _login()
    headers = _headers(token)
    session = _end_upcoming_session(headers)
    sid = session["id"]

    past = (today_ist() - timedelta(days=30)).isoformat()
    patch = client.patch(
        f"/api/v1/sessions/{sid}",
        headers=headers,
        json={"scheduled_date": past},
    )
    assert patch.status_code == 200

    no_reason = client.post(
        "/api/v1/daily-logs",
        headers=headers,
        json={
            "session_id": sid,
            "attendance_status": "PRESENT",
            "activities_done": "Worked on goals today",
        },
    )
    assert no_reason.status_code == 400
    assert "late" in no_reason.json()["detail"].lower()

    ok = client.post(
        "/api/v1/daily-logs",
        headers=headers,
        json={
            "session_id": sid,
            "attendance_status": "PRESENT",
            "activities_done": "Worked on goals today",
            "late_reason": "Submitting after travel",
        },
    )
    assert ok.status_code == 201
    assert ok.json()["approval_status"] == "PENDING"


def test_session_actual_times_serialized_with_timezone():
    token = _login()
    headers = _headers(token)
    body = _end_upcoming_session(headers)
    if body.get("actual_start_at"):
        ts = body["actual_start_at"]
        assert "+" in ts or ts.endswith("Z")
