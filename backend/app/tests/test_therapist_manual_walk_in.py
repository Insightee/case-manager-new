from __future__ import annotations

from datetime import datetime, timedelta, timezone

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


def _session_times():
    today = today_ist()
    start = datetime.combine(today, datetime.min.time()).replace(
        hour=10, minute=0, tzinfo=timezone.utc
    )
    end = start + timedelta(hours=1)
    return today.isoformat(), start.isoformat(), end.isoformat()


def test_manual_walk_in_creates_case_session_and_log():
    token = _login()
    headers = _headers(token)
    scheduled_date, actual_start_at, actual_end_at = _session_times()
    email = f"walkin{int(datetime.now().timestamp())}@testinsighte.com"

    r = client.post(
        "/api/v1/sessions/manual-walk-in",
        headers=headers,
        json={
            "client_name": "Test Parent",
            "client_email": email,
            "child_name": "Walk In Child",
            "scheduled_date": scheduled_date,
            "actual_start_at": actual_start_at,
            "actual_end_at": actual_end_at,
            "mode": "HOME",
        },
    )
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["invite_sent"] is True
    assert data["case_code"]
    session = data["session"]
    assert session["status"] == "COMPLETED"
    assert session["id"]

    log = client.post(
        "/api/v1/daily-logs",
        headers=headers,
        json={
            "session_id": session["id"],
            "attendance_status": "PRESENT",
            "activities_done": "Initial walk-in session activities",
        },
    )
    assert log.status_code == 201, log.text
    assert log.json()["approval_status"] == "PENDING"


def test_manual_walk_in_rejects_duplicate_email():
    token = _login()
    headers = _headers(token)
    scheduled_date, actual_start_at, actual_end_at = _session_times()

    dup = client.post(
        "/api/v1/sessions/manual-walk-in",
        headers=headers,
        json={
            "client_name": "Dup Parent",
            "client_email": "therapist@demo.com",
            "child_name": "Dup Child",
            "scheduled_date": scheduled_date,
            "actual_start_at": actual_start_at,
            "actual_end_at": actual_end_at,
            "mode": "HOME",
        },
    )
    assert dup.status_code == 400
    assert "email" in dup.json()["detail"].lower()


def test_client_intake_deferred_invite_then_start_sends_email():
    token = _login()
    headers = _headers(token)
    email = f"intake{int(datetime.now().timestamp())}@testinsighte.com"

    r = client.post(
        "/api/v1/therapist/client-intake",
        headers=headers,
        json={
            "client_name": "Intake Parent",
            "client_email": email,
            "child_name": "Intake Child",
            "product_module": "homecare",
        },
    )
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["invite_sent"] is False
    case_id = data["case_id"]

    today = today_ist()
    r = client.post(
        "/api/v1/sessions",
        headers=headers,
        json={
            "case_id": case_id,
            "therapist_user_id": 0,
            "scheduled_date": today.isoformat(),
            "start_time": "10:00:00",
            "end_time": "11:00:00",
            "mode": "HOME",
            "status": "SCHEDULED",
        },
    )
    assert r.status_code == 201, r.text
    session_id = r.json()["id"]

    r = client.post(f"/api/v1/sessions/{session_id}/start", headers=headers, json={})
    assert r.status_code == 200, r.text
    assert r.json().get("invite_sent") is True
    assert r.json().get("invite_email") == email
