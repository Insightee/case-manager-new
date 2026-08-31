from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.seed.demo_seed import run as seed_run

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    seed_run()


def _login(email: str) -> dict[str, str]:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "demo123"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_sessions_analytics_status_filter_narrows_total():
    headers = _login("superadmin@demo.com")
    all_res = client.get("/api/v1/admin/sessions/analytics", headers=headers)
    assert all_res.status_code == 200, all_res.text
    all_body = all_res.json()
    all_total = all_body["total_count"]
    assert all_total >= 0

    completed_res = client.get(
        "/api/v1/admin/sessions/analytics?status=COMPLETED",
        headers=headers,
    )
    assert completed_res.status_code == 200, completed_res.text
    completed_body = completed_res.json()
    assert completed_body["total_count"] <= all_total
    assert completed_body["status_counts"].get("COMPLETED", 0) == completed_body["total_count"]
