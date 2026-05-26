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


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_therapist_saves_and_submits_profile():
    token = _login("therapist@demo.com")
    h = _headers(token)

    save = client.put(
        "/api/v1/therapist/profile",
        headers=h,
        json={
            "display_name": "Neha K.",
            "short_bio": "Passionate therapist.",
            "services_offered": ["homecare", "shadow_support"],
        },
    )
    assert save.status_code == 200

    submit = client.post("/api/v1/therapist/profile/submit", headers=h)
    assert submit.status_code == 200
    assert submit.json()["status"] == "PENDING"


def test_admin_approves_profile():
    therapist = _login("therapist@demo.com")
    client.put(
        "/api/v1/therapist/profile",
        headers=_headers(therapist),
        json={"display_name": "Approve Me", "services_offered": ["sports"]},
    )
    client.post("/api/v1/therapist/profile/submit", headers=_headers(therapist))

    admin = _login("superadmin@demo.com")
    pending = client.get("/api/v1/admin/therapist-profiles?status=PENDING", headers=_headers(admin)).json()
    profile = next(p for p in pending if p["display_name"] == "Approve Me")

    approve = client.post(
        f"/api/v1/admin/therapist-profiles/{profile['id']}/approve",
        headers=_headers(admin),
        json={"admin_note": "Looks good"},
    )
    assert approve.status_code == 200
    assert approve.json()["status"] == "APPROVED"


def test_admin_pause_and_delete():
    admin = _login("superadmin@demo.com")
    ah = _headers(admin)
    profiles = client.get("/api/v1/admin/therapist-profiles", headers=ah).json()
    assert profiles
    pid = profiles[0]["id"]

    pause = client.post(f"/api/v1/admin/therapist-profiles/{pid}/pause", headers=ah, json={})
    assert pause.status_code == 200
    assert pause.json()["status"] == "PAUSED"

    resume = client.post(f"/api/v1/admin/therapist-profiles/{pid}/resume", headers=ah)
    assert resume.json()["status"] == "APPROVED"

    del_r = client.delete(f"/api/v1/admin/therapist-profiles/{pid}", headers=ah)
    assert del_r.status_code == 204


def test_invalid_service_category_rejected():
    token = _login("therapist@demo.com")
    r = client.put(
        "/api/v1/therapist/profile",
        headers=_headers(token),
        json={"display_name": "X", "services_offered": ["invalid_service"]},
    )
    assert r.status_code == 400
