from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.seed.demo_seed import run as seed_run

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    seed_run()


def _auth_headers(email: str = "superadmin@demo.com"):
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "demo123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_support_history_list():
    r = client.get("/api/v1/admin/support/history?record_type=all&page_size=10", headers=_auth_headers())
    assert r.status_code == 200
    data = r.json()
    assert "items" in data
    assert "total" in data
    types = {row["record_type"] for row in data["items"]}
    assert "incident" in types, "seeded demo incidents should appear in combined history"


def test_support_history_csv_export():
    r = client.get(
        "/api/v1/admin/support/history/export.csv?record_type=all",
        headers=_auth_headers(),
    )
    assert r.status_code == 200
    assert "record_type" in r.text.splitlines()[0]


def test_therapist_ticket_visible_to_superadmin():
    th_headers = _auth_headers("therapist@demo.com")
    created = client.post(
        "/api/v1/tickets",
        headers=th_headers,
        json={
            "subject": "Test visibility ticket",
            "body": "Automated test ticket body for admin list.",
            "category": "OTHER",
        },
    )
    assert created.status_code == 201

    listed = client.get("/api/v1/tickets?page_size=100", headers=_auth_headers())
    assert listed.status_code == 200
    items = listed.json().get("items") or listed.json()
    if isinstance(items, dict):
        items = items.get("items", [])
    subjects = [t.get("subject") for t in items]
    assert "Test visibility ticket" in subjects
    match = next(t for t in items if t.get("subject") == "Test visibility ticket")
    assert match.get("raised_by_name")
    assert match.get("raised_by_portal") == "Therapist"
