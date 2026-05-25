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


def test_hr_ops_snapshot_read_only_counts():
    r = client.get("/api/v1/hr/ops-snapshot", headers=_login("hr@demo.com"))
    assert r.status_code == 200, r.text
    data = r.json()
    for key in (
        "active_cases",
        "pending_allotment",
        "open_tickets",
        "therapists_active",
        "therapists_pending_profile",
        "pending_leave",
        "iep_missing",
        "observation_checklists_overdue",
    ):
        assert key in data
        assert isinstance(data[key], int)
    assert "approve" not in r.text.lower()


def test_hr_ops_snapshot_requires_hr_access():
    r = client.get("/api/v1/hr/ops-snapshot", headers=_login("therapist@demo.com"))
    assert r.status_code == 403
