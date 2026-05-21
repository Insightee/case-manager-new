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


def test_avatar_upload_and_fetch():
    token = _login("therapist@demo.com")
    headers = {"Authorization": f"Bearer {token}"}
    jpeg = bytes([0xff, 0xd8, 0xff, 0xe0, 0, 0x10, 0x4a, 0x46, 0x49, 0x46, 0, 1, 1, 0, 0, 1, 0, 1, 0, 0, 0xff, 0xd9])
    up = client.post(
        "/api/v1/auth/me/avatar",
        headers=headers,
        files={"file": ("photo.jpg", jpeg, "image/jpeg")},
    )
    assert up.status_code == 200, up.text
    assert up.json()["avatar_url"].startswith("/api/v1/files/avatars/")
    me = client.get("/api/v1/auth/me", headers=headers)
    assert me.json()["avatar_url"]
    av = client.get(me.json()["avatar_url"], headers=headers)
    assert av.status_code == 200
    assert av.headers["content-type"].startswith("image/")


def test_avatar_rejects_oversized():
    token = _login("therapist@demo.com")
    big = b"x" * (1_048_576 + 1)
    r = client.post(
        "/api/v1/auth/me/avatar",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("a.jpg", big, "image/jpeg")},
    )
    assert r.status_code == 400


def test_session_start_end_and_log():
    token = _login("therapist@demo.com")
    headers = {"Authorization": f"Bearer {token}"}
    upcoming = client.get("/api/v1/sessions/upcoming", headers=headers)
    assert upcoming.status_code == 200
    sessions = upcoming.json()
    assert isinstance(sessions, list)
    if not sessions:
        pytest.skip("No scheduled sessions in seed")
    sid = sessions[0]["id"]
    start = client.post(f"/api/v1/sessions/{sid}/start", headers=headers)
    assert start.status_code == 200
    assert start.json()["status"] == "IN_PROGRESS"
    active = client.get("/api/v1/sessions/active", headers=headers)
    assert active.status_code == 200
    assert active.json()["id"] == sid
    end = client.post(f"/api/v1/sessions/{sid}/end", headers=headers)
    assert end.status_code == 200
    assert end.json()["status"] == "COMPLETED"
    log = client.post(
        "/api/v1/daily-logs",
        headers=headers,
        json={
            "session_id": sid,
            "attendance_status": "PRESENT",
            "activities_done": "Play therapy",
            "goals_addressed": "Communication",
            "parent_notes": "Good session",
        },
    )
    assert log.status_code == 201
    assert log.json()["goals_addressed"] == "Communication"


def test_parent_session_logs_omit_internal_fields():
    therapist_token = _login("therapist@demo.com")
    th = {"Authorization": f"Bearer {therapist_token}"}
    upcoming = client.get("/api/v1/sessions/upcoming", headers=th).json()
    if not upcoming:
        pytest.skip("No scheduled sessions")
    sid = upcoming[0]["id"]
    client.post(f"/api/v1/sessions/{sid}/start", headers=th)
    client.post(f"/api/v1/sessions/{sid}/end", headers=th)
    created = client.post(
        "/api/v1/daily-logs",
        headers=th,
        json={
            "session_id": sid,
            "attendance_status": "PRESENT",
            "session_notes": "internal only",
            "observations": "clinical internal",
            "parent_notes": "visible to parent",
        },
    )
    assert created.status_code == 201
    log_id = created.json()["id"]
    mgr_token = _login("casemanager@demo.com")
    approve = client.post(f"/api/v1/daily-logs/{log_id}/approve", headers={"Authorization": f"Bearer {mgr_token}"})
    assert approve.status_code == 200
    parent_token = _login("parent@demo.com")
    pr = client.get("/api/v1/parent/session-logs", headers={"Authorization": f"Bearer {parent_token}"})
    assert pr.status_code == 200
    rows = pr.json()
    row = next((r for r in rows if r.get("parent_notes") == "visible to parent"), None)
    assert row is not None, "Approved log with parent_notes should appear for parent"
    assert "observations" not in row
    assert "session_notes" not in row


def test_cannot_start_two_sessions():
    token = _login("therapist@demo.com")
    headers = {"Authorization": f"Bearer {token}"}
    upcoming = client.get("/api/v1/sessions/upcoming", headers=headers).json()
    if len(upcoming) < 2:
        pytest.skip("Need two scheduled sessions")
    s1, s2 = upcoming[0]["id"], upcoming[1]["id"]
    assert client.post(f"/api/v1/sessions/{s1}/start", headers=headers).status_code == 200
    second = client.post(f"/api/v1/sessions/{s2}/start", headers=headers)
    assert second.status_code == 400
    client.post(f"/api/v1/sessions/{s1}/end", headers=headers)
