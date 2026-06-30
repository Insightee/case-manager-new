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


def _submit_profile(token: str, payload: dict) -> dict:
    r = client.post("/api/v1/therapist/profile/submit", headers=_headers(token), json=payload)
    assert r.status_code == 200
    return r.json()


def _therapist_profile(token: str) -> dict:
    return client.get("/api/v1/therapist/profile", headers=_headers(token)).json()


def _pending_profile_for_therapist(admin_token: str, therapist_token: str) -> dict:
    prof = _therapist_profile(therapist_token)
    pending = client.get("/api/v1/admin/therapist-profiles?status=PENDING", headers=_headers(admin_token)).json()
    return next(p for p in pending if p["user_id"] == prof["user_id"])


def test_therapist_submits_profile_for_first_approval():
    token = _login("therapist@demo.com")
    body = _submit_profile(
        token,
        {
            "display_name": "Neha K.",
            "short_bio": "Passionate therapist.",
            "services_offered": ["homecare", "shadow_support"],
        },
    )
    assert body["status"] in ("PENDING", "APPROVED")
    if body["status"] == "PENDING":
        assert body["has_pending_changes"] is False
    else:
        assert body["has_pending_changes"] is True


def test_admin_approves_profile():
    therapist = _login("therapist@demo.com")
    _submit_profile(
        therapist,
        {"display_name": "Approve Me", "services_offered": ["sports"]},
    )

    admin = _login("superadmin@demo.com")
    profile = _pending_profile_for_therapist(admin, therapist)
    if profile.get("pending_submission"):
        assert profile["pending_submission"]["display_name"] == "Approve Me"
    else:
        assert profile["display_name"] == "Approve Me"

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
    r = client.post(
        "/api/v1/therapist/profile/submit",
        headers=_headers(token),
        json={"display_name": "X", "services_offered": ["invalid_service"]},
    )
    assert r.status_code == 400


def test_therapist_edit_start_date_approval_flow():
    therapist = _login("therapist@demo.com")
    th = _headers(therapist)

    r = client.post(
        "/api/v1/therapist/profile/submit",
        headers=th,
        json={
            "display_name": "Neha K.",
            "services_offered": ["homecare"],
            "employment_start_date": "2021-06-15",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["employment_start_date"] == "2021-06-15"
    assert body["status"] in ("PENDING", "APPROVED")

    admin = _login("superadmin@demo.com")
    profile = _pending_profile_for_therapist(admin, therapist)

    r = client.post(
        f"/api/v1/admin/therapist-profiles/{profile['id']}/approve",
        headers=_headers(admin),
        json={"admin_note": "Approved start date"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "APPROVED"
    assert r.json()["employment_start_date"] == "2021-06-15"


def test_approved_snapshot_enables_review_diff():
    therapist = _login("therapist@demo.com")
    th = _headers(therapist)

    _submit_profile(
        therapist,
        {
            "display_name": "Diff Tester",
            "short_bio": "Original bio.",
            "services_offered": ["homecare"],
        },
    )

    admin = _login("superadmin@demo.com")
    profile = _pending_profile_for_therapist(admin, therapist)
    approved = client.post(
        f"/api/v1/admin/therapist-profiles/{profile['id']}/approve",
        headers=_headers(admin),
        json={},
    ).json()
    snap = approved["approved_snapshot"]
    assert snap is not None
    assert snap["short_bio"] == "Original bio."
    assert snap["services_offered"] == ["homecare"]

    edited = _submit_profile(
        therapist,
        {
            "display_name": "Diff Tester",
            "short_bio": "Updated bio with new details.",
            "services_offered": ["homecare", "shadow_support"],
        },
    )
    assert edited["status"] == "APPROVED"
    assert edited["has_pending_changes"] is True
    assert edited["short_bio"] == "Original bio."
    assert edited["pending_submission"]["short_bio"] == "Updated bio with new details."
    assert edited["approved_snapshot"]["short_bio"] == "Original bio."


def test_approved_therapist_stays_allotment_eligible_with_pending_changes():
    therapist = _login("therapist@demo.com")
    th = _headers(therapist)

    _submit_profile(
        therapist,
        {"display_name": "Allotment Tester", "services_offered": ["homecare"]},
    )

    admin = _login("superadmin@demo.com")
    ah = _headers(admin)
    profile = _pending_profile_for_therapist(admin, therapist)
    client.post(f"/api/v1/admin/therapist-profiles/{profile['id']}/approve", headers=ah, json={})

    _submit_profile(
        therapist,
        {
            "display_name": "Allotment Tester",
            "short_bio": "New bio pending review.",
            "services_offered": ["homecare"],
        },
    )

    therapists = client.get(
        "/api/v1/admin/allotment/therapists?product_module=homecare",
        headers=ah,
    ).json()
    match = next((t for t in therapists if t["therapist_name"] and "Allotment" in (t.get("full_name") or t["therapist_name"])), None)
    if match is None:
        user_id = profile["user_id"]
        match = next((t for t in therapists if t["therapist_user_id"] == user_id), None)
    assert match is not None
    assert match["profile_status"] == "APPROVED"
