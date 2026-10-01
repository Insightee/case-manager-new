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


def _post_usage_chunk(token: str, *, idempotency_key: str):
    ended_at = datetime.now(timezone.utc)
    started_at = ended_at - timedelta(minutes=2)
    usage = {
        "chunks": [
            {
                "session_id": f"sess-{idempotency_key}",
                "portal": "admin",
                "route": "/admin/platform-stats",
                "active_seconds": 90,
                "idle_seconds": 5,
                "hidden_seconds": 0,
                "started_at": started_at.isoformat(),
                "ended_at": ended_at.isoformat(),
                "idempotency_key": idempotency_key,
            }
        ]
    }
    batch = client.post(
        "/api/v1/auth/activity/batch",
        headers={"Authorization": f"Bearer {token}"},
        json=usage,
    )
    assert batch.status_code == 200


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
    _post_usage_chunk(token, idempotency_key="platform-stats-test-1")

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
    assert "recent_users" not in body
    assert any(item.get("portal") == "admin" for item in body["by_portal"])


def test_platform_stats_activity_pagination_search_and_filters():
    token = _login("superadmin@demo.com")
    _login("superadmin@demo.com")
    _post_usage_chunk(token, idempotency_key="platform-stats-activity-1")

    res = client.get(
        "/api/v1/admin/platform-stats/activity?days=7&page=1&limit=10",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["total"] >= 1
    assert body["page"] == 1
    assert body["limit"] == 10
    assert len(body["items"]) >= 1
    assert "user_email" in body["items"][0]

    search = client.get(
        "/api/v1/admin/platform-stats/activity?days=7&q=superadmin",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert search.status_code == 200
    assert search.json()["total"] >= 1
    assert all(
        "superadmin" in (row.get("user_email") or "").lower()
        or "superadmin" in (row.get("user_name") or "").lower()
        for row in search.json()["items"]
    )

    logged_in = client.get(
        "/api/v1/admin/platform-stats/activity?days=7&status=logged_in",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert logged_in.status_code == 200
    assert all(row.get("logged_in_period") for row in logged_in.json()["items"])

    active_now = client.get(
        "/api/v1/admin/platform-stats/activity?days=7&status=active_now",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert active_now.status_code == 200
    assert all(row.get("active_now") for row in active_now.json()["items"])

    bad_status = client.get(
        "/api/v1/admin/platform-stats/activity?status=not-a-filter",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert bad_status.status_code == 400
