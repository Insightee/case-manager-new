from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.seed.demo_seed import run as seed_run

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    seed_run()


def _login(email: str, password: str = "demo123") -> str:
    res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200
    return res.json()["access_token"]


def test_platform_stats_requires_super_admin():
    token = _login("casemanager@demo.com")
    res = client.get(
        "/api/v1/admin/platform-stats",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 403


def test_platform_stats_contract_and_login_count():
    token = _login("superadmin@demo.com")
    _login("superadmin@demo.com")

    ended_at = datetime.now(timezone.utc)
    started_at = ended_at - timedelta(minutes=2)
    usage = {
        "chunks": [
            {
                "session_id": "sess-platform-stats-1",
                "portal": "admin",
                "route": "/admin/platform-stats",
                "active_seconds": 90,
                "idle_seconds": 5,
                "hidden_seconds": 0,
                "started_at": started_at.isoformat(),
                "ended_at": ended_at.isoformat(),
                "idempotency_key": "platform-stats-test-1",
            }
        ]
    }
    batch = client.post(
        "/api/v1/auth/activity/batch",
        headers={"Authorization": f"Bearer {token}"},
        json=usage,
    )
    assert batch.status_code == 200

    res = client.get(
        "/api/v1/admin/platform-stats?days=7",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["timezone"] == "Asia/Kolkata"
    assert "summary" in body
    assert body["summary"]["unique_logins"] >= 1
    assert body["summary"]["login_events"] >= 1
    assert "by_portal" in body
    assert "by_role" in body
    assert "recent_users" in body
    assert any(item.get("portal") == "admin" for item in body["by_portal"])
