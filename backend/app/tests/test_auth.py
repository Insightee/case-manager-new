from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.seed.demo_seed import run as seed_run

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    seed_run()


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_login_and_me():
    r = client.post("/api/v1/auth/login", json={"email": "therapist@demo.com", "password": "demo123"})
    assert r.status_code == 200
    token = r.json()["access_token"]
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert "THERAPIST" in me.json()["roles"]


def test_parent_cannot_see_internal_reports():
    r = client.post("/api/v1/auth/login", json={"email": "parent@demo.com", "password": "demo123"})
    token = r.json()["access_token"]
    reports = client.get("/api/v1/parent/reports", headers={"Authorization": f"Bearer {token}"})
    assert reports.status_code == 200
    for report in reports.json():
        assert report["status"] == "approved"
