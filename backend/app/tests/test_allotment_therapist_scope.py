"""Allotment therapist list respects therapist service profiles."""

from __future__ import annotations

import uuid

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


def _therapist_ids(product_module: str, *, approved_only: bool = True) -> set[int]:
    headers = _login("superadmin@demo.com")
    res = client.get(
        f"/api/v1/admin/allotment/therapists?product_module={product_module}&approved_only={str(approved_only).lower()}",
        headers=headers,
    )
    assert res.status_code == 200, res.text
    return {row["therapist_user_id"] for row in res.json()}


def _onboard_shadow_therapist() -> tuple[int, int]:
    headers = _login("superadmin@demo.com")
    cm_id = client.get("/api/v1/auth/me", headers=_login("casemanager@demo.com")).json()["id"]
    email = f"shadow-only-{uuid.uuid4().hex[:8]}@example.com"
    res = client.post(
        "/api/v1/admin/therapists/onboard",
        headers=headers,
        json={
            "email": email,
            "full_name": "Shadow Only Therapist",
            "mode": "direct",
            "password": "demo12345",
            "services_offered": ["shadow_support"],
            "module_assignments": ["shadow_support"],
            "primary_case_manager_user_id": cm_id,
            "send_email": False,
        },
    )
    assert res.status_code == 200, res.text
    user_id = res.json()["user_id"]
    profile_id = res.json()["profile_id"]
    return user_id, profile_id


def test_shadow_only_therapist_not_listed_for_homecare():
    user_id, _ = _onboard_shadow_therapist()
    homecare_ids = _therapist_ids("homecare", approved_only=False)
    shadow_ids = _therapist_ids("shadow_support", approved_only=False)
    assert user_id in shadow_ids
    assert user_id not in homecare_ids


def test_adding_homecare_to_profile_includes_therapist_for_homecare():
    user_id, profile_id = _onboard_shadow_therapist()
    headers = _login("superadmin@demo.com")
    patch = client.patch(
        f"/api/v1/admin/therapist-profiles/{profile_id}",
        headers=headers,
        json={"services_offered": ["shadow_support", "homecare"]},
    )
    assert patch.status_code == 200, patch.text
    homecare_ids = _therapist_ids("homecare", approved_only=False)
    assert user_id in homecare_ids


def test_removing_homecare_excludes_therapist_from_homecare():
    user_id, profile_id = _onboard_shadow_therapist()
    headers = _login("superadmin@demo.com")
    add = client.patch(
        f"/api/v1/admin/therapist-profiles/{profile_id}",
        headers=headers,
        json={"services_offered": ["shadow_support", "homecare"]},
    )
    assert add.status_code == 200, add.text
    remove = client.patch(
        f"/api/v1/admin/therapist-profiles/{profile_id}",
        headers=headers,
        json={"services_offered": ["shadow_support"]},
    )
    assert remove.status_code == 200, remove.text
    homecare_ids = _therapist_ids("homecare", approved_only=False)
    assert user_id not in homecare_ids
