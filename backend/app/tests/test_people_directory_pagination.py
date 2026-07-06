"""Paginated People directory endpoints."""

from fastapi.testclient import TestClient

from app.main import app
from app.seed.demo_seed import run as seed_run

client = TestClient(app)


def setup_module():
    seed_run()


def _login(email: str) -> dict[str, str]:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "demo123"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_users_directory_paginated_therapists():
    headers = _login("superadmin@demo.com")
    res = client.get(
        "/api/v1/admin/users/directory?roles=THERAPIST&active_only=false&page=1&page_size=15&sort=id_asc",
        headers=headers,
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert "items" in body
    assert body["total"] >= 1


def test_families_paginated():
    headers = _login("superadmin@demo.com")
    res = client.get("/api/v1/admin/families?page=1&page_size=15", headers=headers)
    assert res.status_code == 200, res.text
    body = res.json()
    assert "items" in body
    assert body["total"] >= 0
