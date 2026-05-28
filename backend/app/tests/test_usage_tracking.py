from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.seed.demo_seed import run as seed_run

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    seed_run()


def _login(email: str, password: str) -> str:
    res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200
    return res.json()["access_token"]


def test_activity_batch_is_idempotent():
    token = _login("superadmin@demo.com", "demo123")
    payload = {
        "chunks": [
            {
                "session_id": "sess-usage-1",
                "portal": "admin",
                "route": "/admin",
                "active_seconds": 120,
                "idle_seconds": 10,
                "hidden_seconds": 5,
                "started_at": "2026-05-28T06:00:00Z",
                "ended_at": "2026-05-28T06:02:00Z",
                "idempotency_key": "usage-batch-1",
            }
        ]
    }
    first = client.post(
        "/api/v1/auth/activity/batch",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
    )
    assert first.status_code == 200
    assert first.json()["inserted"] == 1

    second = client.post(
        "/api/v1/auth/activity/batch",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
    )
    assert second.status_code == 200
    assert second.json()["inserted"] == 0
    assert second.json()["duplicates"] == 1


def test_usage_summary_contract_stays_stable():
    token = _login("superadmin@demo.com", "demo123")
    summary = client.get(
        "/api/v1/admin/audit/app-usage-summary?days=7&portal=admin",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert summary.status_code == 200
    body = summary.json()
    assert "range" in body
    assert "items" in body
    assert "total_active_seconds" in body
