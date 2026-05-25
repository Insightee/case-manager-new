from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.seed.demo_seed import run as seed_run

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    seed_run()


def _login(email: str) -> str:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "demo123"})
    assert r.status_code == 200
    return r.json()["access_token"]


def test_therapist_home():
    token = _login("therapist@demo.com")
    headers = {"Authorization": f"Bearer {token}"}
    r = client.get("/api/v1/therapist/home", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert "stats" in data
    assert "cases_board" in data
    assert "allCases" in data["cases_board"] or "allCases" in data.get("cases_board", {})
    board = data["cases_board"]
    assert "stats" in board
    assert "sections" in board
    assert data["stats"]["case_count"] >= 0


def test_therapist_sessions_workspace():
    token = _login("therapist@demo.com")
    headers = {"Authorization": f"Bearer {token}"}
    r = client.get("/api/v1/therapist/sessions/workspace", headers=headers)
    assert r.status_code == 200
    assert "upcoming" in r.json()
    assert "needs_log" in r.json()


def test_therapist_reports_pipeline():
    token = _login("therapist@demo.com")
    headers = {"Authorization": f"Bearer {token}"}
    r = client.get("/api/v1/therapist/reports/pipeline", headers=headers)
    assert r.status_code == 200
    assert "pipeline" in r.json()


def test_parent_home():
    token = _login("parent@demo.com")
    headers = {"Authorization": f"Bearer {token}"}
    r = client.get("/api/v1/parent/home", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert "stats" in data
    assert "cases" in data
    assert "recent_updates" in data


def test_parent_session_logs_have_friendly_fields():
    token = _login("parent@demo.com")
    headers = {"Authorization": f"Bearer {token}"}
    r = client.get("/api/v1/parent/session-logs", headers=headers)
    assert r.status_code == 200
    logs = r.json()
    for log in logs:
        assert "attendance_label" in log
        if log.get("headline"):
            assert "session_notes" not in log or log.get("session_notes") is None


def test_admin_home_and_audit():
    token = _login("superadmin@demo.com")
    headers = {"Authorization": f"Bearer {token}"}
    home = client.get("/api/v1/admin/home", headers=headers)
    assert home.status_code == 200
    body = home.json()
    assert "widgets" in body
    assert "workbench" not in body
    audit = client.get("/api/v1/admin/audit", headers=headers, params={"limit": 5})
    assert audit.status_code == 200
    assert "items" in audit.json()
