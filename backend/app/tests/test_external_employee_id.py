from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.seed.demo_seed import run as seed_run

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    seed_run()


def _login(email: str = "superadmin@demo.com") -> dict[str, str]:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "demo123"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_onboard_therapist_with_external_employee_id_direct():
    headers = _login()
    suffix = uuid.uuid4().hex[:8]
    therapist_id = f"T-{suffix}"
    email = f"ext-id-{suffix}@example.com"
    cm_id = client.get("/api/v1/auth/me", headers=_login("casemanager@demo.com")).json()["id"]
    res = client.post(
        "/api/v1/admin/therapists/onboard",
        headers=headers,
        json={
            "email": email,
            "full_name": "External ID Therapist",
            "external_employee_id": therapist_id,
            "mode": "direct",
            "password": "demo12345",
            "services_offered": ["homecare"],
            "primary_case_manager_user_id": cm_id,
        },
    )
    assert res.status_code == 200, res.text
    user_id = res.json()["user_id"]
    detail = client.get(f"/api/v1/admin/users/{user_id}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["external_employee_id"] == therapist_id


def test_external_employee_id_must_be_unique():
    headers = _login()
    suffix = uuid.uuid4().hex[:8]
    therapist_id = f"DUP-{suffix}"
    cm_id = client.get("/api/v1/auth/me", headers=_login("casemanager@demo.com")).json()["id"]
    first = client.post(
        "/api/v1/admin/therapists/onboard",
        headers=headers,
        json={
            "email": f"dup-a-{suffix}@example.com",
            "full_name": "Dup A",
            "external_employee_id": therapist_id,
            "mode": "direct",
            "password": "demo12345",
            "services_offered": ["homecare"],
            "primary_case_manager_user_id": cm_id,
        },
    )
    assert first.status_code == 200, first.text
    second = client.post(
        "/api/v1/admin/therapists/onboard",
        headers=headers,
        json={
            "email": f"dup-b-{suffix}@example.com",
            "full_name": "Dup B",
            "external_employee_id": therapist_id,
            "mode": "direct",
            "password": "demo12345",
            "services_offered": ["homecare"],
            "primary_case_manager_user_id": cm_id,
        },
    )
    assert second.status_code == 400
    assert "already assigned" in second.json()["detail"].lower()


def test_patch_external_employee_id():
    headers = _login()
    suffix = uuid.uuid4().hex[:8]
    cm_id = client.get("/api/v1/auth/me", headers=_login("casemanager@demo.com")).json()["id"]
    created = client.post(
        "/api/v1/admin/therapists/onboard",
        headers=headers,
        json={
            "email": f"patch-{suffix}@example.com",
            "full_name": "Patch Me",
            "mode": "direct",
            "password": "demo12345",
            "services_offered": ["homecare"],
            "primary_case_manager_user_id": cm_id,
        },
    )
    assert created.status_code == 200, created.text
    user_id = created.json()["user_id"]
    new_id = f"PATCH-{suffix}"
    patched = client.patch(
        f"/api/v1/admin/users/{user_id}",
        headers=headers,
        json={"external_employee_id": new_id},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["external_employee_id"] == new_id
