from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from sqlalchemy import select

from app.core.database import SessionLocal
from app.main import app
from app.models.therapist_profile import TherapistProfile, TherapistProfileStatus
from app.models.user import User
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


def _profile_items(response) -> list[dict]:
    body = response.json()
    if isinstance(body, list):
        return body
    return body.get("items", [])


def _ensure_reviewable_contact(token: str) -> None:
    r = client.patch(
        "/api/v1/auth/me",
        headers=_headers(token),
        json={
            "phone": "9876543210",
            "home_address_line1": "12 MG Road",
            "home_city": "Bengaluru",
            "home_pincode": "560001",
        },
    )
    assert r.status_code == 200


def _set_avatar(email: str) -> None:
    db = SessionLocal()
    try:
        user = db.scalar(select(User).where(User.email == email))
        assert user is not None
        user.avatar_path = "avatars/quality-test.png"
        db.commit()
    finally:
        db.close()


def _submit_profile(token: str, payload: dict) -> dict:
    _ensure_reviewable_contact(token)
    body = {
        "professional_qualification_entries": [{"kind": "degree", "title": "B.Ed", "year": 2018}],
        **payload,
    }
    r = client.post("/api/v1/therapist/profile/submit", headers=_headers(token), json=body)
    assert r.status_code == 200, r.text
    return r.json()


def _therapist_profile(token: str) -> dict:
    return client.get("/api/v1/therapist/profile", headers=_headers(token)).json()


def _pending_profile_for_therapist(admin_token: str, therapist_token: str) -> dict:
    prof = _therapist_profile(therapist_token)
    pending = _profile_items(
        client.get("/api/v1/admin/therapist-profiles?status=PENDING&page_size=100", headers=_headers(admin_token))
    )
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


def test_admin_pause_delete_restore_soft_delete():
    admin = _login("superadmin@demo.com")
    ah = _headers(admin)
    profiles = _profile_items(client.get("/api/v1/admin/therapist-profiles?page_size=100", headers=ah))
    assert profiles
    pid = profiles[0]["id"]

    pause = client.post(f"/api/v1/admin/therapist-profiles/{pid}/pause", headers=ah, json={})
    assert pause.status_code == 200
    assert pause.json()["status"] == "PAUSED"

    resume = client.post(f"/api/v1/admin/therapist-profiles/{pid}/resume", headers=ah)
    assert resume.json()["status"] == "APPROVED"

    del_r = client.delete(f"/api/v1/admin/therapist-profiles/{pid}", headers=ah)
    assert del_r.status_code == 204

    active = _profile_items(client.get("/api/v1/admin/therapist-profiles?page_size=100", headers=ah))
    assert not any(p["id"] == pid for p in active)

    deleted = _profile_items(client.get("/api/v1/admin/therapist-profiles?status=DELETED&page_size=100", headers=ah))
    match = next(p for p in deleted if p["id"] == pid)
    assert match["status"] == "DELETED"
    assert match.get("deleted_at")

    restore = client.post(f"/api/v1/admin/therapist-profiles/{pid}/restore", headers=ah)
    assert restore.status_code == 200
    assert restore.json()["status"] == "PAUSED"

    # Leave demo therapist allotment-eligible for later tests in this module.
    resumed = client.post(f"/api/v1/admin/therapist-profiles/{pid}/resume", headers=ah)
    assert resumed.status_code == 200
    assert resumed.json()["status"] == "APPROVED"


def test_therapist_profiles_summary_includes_new_kpis():
    admin = _login("superadmin@demo.com")
    summary = client.get("/api/v1/admin/therapist-profiles/summary", headers=_headers(admin))
    assert summary.status_code == 200
    body = summary.json()
    assert "needs_listing" in body
    assert "DELETED" in body
    assert "no_sessions_15d" in body
    assert "no_profile" in body


def test_needs_listing_filter_returns_users_without_profiles():
    admin = _login("superadmin@demo.com")
    ah = _headers(admin)
    rows = _profile_items(client.get("/api/v1/admin/therapist-profiles?status=NEEDS_LISTING&page_size=100", headers=ah))
    for row in rows:
        assert row["status"] == "NEEDS_LISTING"
        assert row["id"] is None
        assert row["user_id"]


def test_activity_filter_no_sessions_15d():
    admin = _login("superadmin@demo.com")
    ah = _headers(admin)
    res = client.get("/api/v1/admin/therapist-profiles?activity=no_sessions_15d&page_size=100", headers=ah)
    assert res.status_code == 200
    body = res.json()
    assert "items" in body
    assert "total" in body
    rows = body["items"]
    for row in rows:
        assert row["status"] != "DELETED"
        if row.get("last_session_log_at"):
            assert row.get("days_since_last_session_log") is None or row["days_since_last_session_log"] >= 15


def test_audit_backfill_recreates_deleted_profile_stub():
    from datetime import datetime, timezone

    from app.core.audit import log_audit
    from app.core.database import get_db
    from app.models.therapist_profile import TherapistProfile, TherapistProfileStatus
    from app.models.user import User
    from app.services.therapist_profile_backfill_service import backfill_deleted_profiles_from_audit

    therapist = _login("therapist@demo.com")
    prof = _therapist_profile(therapist)
    profile_id = prof["id"]
    user_id = prof["user_id"]

    db = next(get_db())
    try:
        profile = db.get(TherapistProfile, profile_id)
        assert profile is not None
        log_audit(
            db,
            actor_user_id=user_id,
            action="delete",
            entity_type="therapist_profile",
            entity_id=profile_id,
            old_value={"user_id": user_id, "display_name": profile.display_name},
        )
        db.delete(profile)
        db.commit()
        assert db.get(TherapistProfile, profile_id) is None

        created = backfill_deleted_profiles_from_audit(db)
        db.commit()
        assert created >= 1
        restored = db.scalars(select(TherapistProfile).where(TherapistProfile.user_id == user_id)).first()
        assert restored is not None
        assert restored.status == TherapistProfileStatus.DELETED
        assert restored.deleted_at is not None
    finally:
        db.close()

    admin = _login("superadmin@demo.com")
    ah = _headers(admin)
    deleted_rows = _profile_items(
        client.get("/api/v1/admin/therapist-profiles?status=DELETED&page_size=100", headers=ah)
    )
    assert any(row["user_id"] == user_id for row in deleted_rows)

    backfilled_id = next(row["id"] for row in deleted_rows if row["user_id"] == user_id)
    restore = client.post(f"/api/v1/admin/therapist-profiles/{backfilled_id}/restore", headers=ah)
    assert restore.status_code == 200
    resumed = client.post(f"/api/v1/admin/therapist-profiles/{backfilled_id}/resume", headers=ah)
    assert resumed.status_code == 200
    assert resumed.json()["status"] == "APPROVED"


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

    body = _submit_profile(
        therapist,
        {
            "display_name": "Neha K.",
            "services_offered": ["homecare"],
            "employment_start_date": "2021-06-15",
        },
    )
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


def test_therapist_profiles_pagination():
    admin = _login("superadmin@demo.com")
    ah = _headers(admin)
    page1 = client.get("/api/v1/admin/therapist-profiles?page=1&page_size=2", headers=ah)
    assert page1.status_code == 200
    body1 = page1.json()
    assert "items" in body1
    assert body1["page"] == 1
    assert body1["page_size"] == 2
    assert len(body1["items"]) <= 2
    if body1["total"] > 2:
        page2 = client.get("/api/v1/admin/therapist-profiles?page=2&page_size=2", headers=ah).json()
        assert page2["page"] == 2
        ids1 = {row["id"] for row in body1["items"] if row.get("id") is not None}
        ids2 = {row["id"] for row in page2["items"] if row.get("id") is not None}
        assert ids1.isdisjoint(ids2)


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


FORTY_ONE_WORDS = " ".join(["support"] * 41)


def test_submit_below_50_is_rejected():
    token = _login("therapist@demo.com")
    db = SessionLocal()
    try:
        user = db.scalar(select(User).where(User.email == "therapist@demo.com"))
        user.avatar_path = None
        user.phone = None
        db.commit()
    finally:
        db.close()
    r = client.post(
        "/api/v1/therapist/profile/submit",
        headers=_headers(token),
        json={
            "display_name": "Low Score",
            "services_offered": ["homecare"],
            "short_bio": "Hi",
            "professional_qualification_entries": [],
        },
    )
    assert r.status_code == 400
    detail = r.json()["detail"]
    assert "still need a few details" in (detail.get("message") if isinstance(detail, dict) else str(detail))


def test_mid_quality_submit_goes_to_pending():
    token = _login("therapist@demo.com")
    body = _submit_profile(
        token,
        {"display_name": "Mid Score", "services_offered": ["homecare"], "short_bio": "Short listing bio."},
    )
    assert body["status"] in ("PENDING", "APPROVED")
    if body["status"] == "APPROVED":
        assert body["has_pending_changes"] is True
    else:
        assert body["quality"]["auto_pass"] is False
        assert body["quality"]["can_submit"] is True


def test_high_quality_submit_auto_approves():
    _set_avatar("therapist@demo.com")
    token = _login("therapist@demo.com")
    body = _submit_profile(
        token,
        {
            "display_name": "Auto Pass",
            "short_bio": FORTY_ONE_WORDS,
            "services_offered": ["homecare"],
            "professional_qualification_entries": [{"kind": "degree", "title": "M.Sc. Psychology", "year": 2019}],
        },
    )
    assert body["status"] == "APPROVED"
    assert body["has_pending_changes"] is False
    assert body["quality"]["auto_pass"] is True
    assert "Auto-approved" in (body.get("admin_note") or "")


def test_admin_request_changes_then_resubmit():
    token = _login("therapist@demo.com")
    db = SessionLocal()
    try:
        user = db.scalar(select(User).where(User.email == "therapist@demo.com"))
        profile = db.scalar(select(TherapistProfile).where(TherapistProfile.user_id == user.id))
        user.avatar_path = None
        profile.approved_snapshot = None
        profile.pending_submission = None
        profile.status = TherapistProfileStatus.DRAFT
        profile.admin_note = None
        db.commit()
    finally:
        db.close()
    body = _submit_profile(
        token,
        {"display_name": "Needs Tweaks", "services_offered": ["homecare"], "short_bio": "Needs more work."},
    )
    assert body["status"] == "PENDING"
    admin = _login("superadmin@demo.com")
    profile = _pending_profile_for_therapist(admin, token)
    r = client.post(
        f"/api/v1/admin/therapist-profiles/{profile['id']}/request-changes",
        headers=_headers(admin),
        json={"admin_note": "Please add a fuller bio and check the photo."},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "CHANGES_REQUESTED"
    assert "fuller bio" in (r.json().get("admin_note") or "")
    resubmit = _submit_profile(
        token,
        {"display_name": "Needs Tweaks", "services_offered": ["homecare"], "short_bio": "Still short after updates."},
    )
    assert resubmit["status"] == "PENDING"
    assert resubmit.get("admin_note") is None


def test_resubmit_below_80_stages_pending_submission():
    _set_avatar("therapist@demo.com")
    token = _login("therapist@demo.com")
    first = _submit_profile(
        token,
        {
            "display_name": "Live Listing",
            "short_bio": FORTY_ONE_WORDS,
            "services_offered": ["homecare"],
            "professional_qualification_entries": [{"kind": "degree", "title": "M.Sc. Psychology", "year": 2019}],
        },
    )
    assert first["status"] == "APPROVED"
    assert first["has_pending_changes"] is False
    second = _submit_profile(
        token,
        {
            "display_name": "Pending Edit",
            "short_bio": "Shorter public bio.",
            "services_offered": ["homecare"],
        },
    )
    assert second["status"] == "APPROVED"
    assert second["has_pending_changes"] is True
    assert second["pending_submission"]["display_name"] == "Pending Edit"
    assert second["quality"]["auto_pass"] is False
