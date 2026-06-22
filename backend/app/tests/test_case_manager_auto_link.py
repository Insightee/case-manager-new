"""Case manager auto-links from therapist primary CM on assignment and allotment."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.database import SessionLocal
from app.main import app
from app.models.case import Case
from app.models.therapist_profile import TherapistProfile
from app.models.user import User
from app.seed.demo_seed import run as seed_run

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    seed_run()


def _login(email: str) -> str:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "demo123"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _set_therapist_primary_cm(therapist_user_id: int, cm_user_id: int) -> None:
    db = SessionLocal()
    try:
        profile = db.scalars(
            select(TherapistProfile).where(TherapistProfile.user_id == therapist_user_id)
        ).first()
        assert profile is not None
        profile.supervisor_user_id = cm_user_id
        db.commit()
    finally:
        db.close()


def _get_user_id(email: str) -> int:
    db = SessionLocal()
    try:
        user = db.scalars(select(User).where(User.email == email)).first()
        assert user is not None
        return user.id
    finally:
        db.close()


def test_allot_links_case_manager_from_therapist_primary_cm():
    suffix = uuid.uuid4().hex[:8]
    admin = _login("superadmin@demo.com")
    ah = _headers(admin)
    cm_id = _get_user_id("casemanager@demo.com")

    therapists = client.get(
        "/api/v1/admin/allotment/therapists?product_module=homecare&approved_only=false",
        headers=ah,
    ).json()
    therapist_id = therapists[0]["therapist_user_id"]
    _set_therapist_primary_cm(therapist_id, cm_id)

    fam = client.post(
        "/api/v1/admin/families",
        headers=ah,
        json={
            "parent_email": f"cm-link-parent-{suffix}@demo.com",
            "parent_full_name": "CM Link Parent",
            "child": {"first_name": "CM", "last_name": suffix},
            "send_invite": False,
        },
    )
    assert fam.status_code == 201, fam.text
    child_id = fam.json()["childId"]

    allot = client.post(
        "/api/v1/admin/cases/allot",
        headers=_headers(_login("casemanager@demo.com")),
        json={
            "child_id": child_id,
            "service_type": "Homecare",
            "product_module": "homecare",
            "billing_type": "PER_SESSION",
            "compensation_mode": "PERCENTAGE",
            "client_billing_mode": "POSTPAID",
            "client_rate_per_session_inr": 1200,
            "pay_share_amount_inr": 720,
            "therapist_user_id": therapist_id,
        },
    )
    assert allot.status_code == 201, allot.text
    case_id = allot.json()["case"]["id"]

    db = SessionLocal()
    try:
        case = db.get(Case, case_id)
        assert case is not None
        assert case.case_manager_user_id == cm_id
    finally:
        db.close()


def test_allot_overwrites_existing_case_manager_with_therapist_primary_cm():
    suffix = uuid.uuid4().hex[:8]
    admin = _login("superadmin@demo.com")
    ah = _headers(admin)
    cm_id = _get_user_id("casemanager@demo.com")
    other_cm_id = _get_user_id("superadmin@demo.com")

    therapists = client.get(
        "/api/v1/admin/allotment/therapists?product_module=homecare&approved_only=false",
        headers=ah,
    ).json()
    therapist_id = therapists[0]["therapist_user_id"]
    _set_therapist_primary_cm(therapist_id, cm_id)

    fam = client.post(
        "/api/v1/admin/families",
        headers=ah,
        json={
            "parent_email": f"cm-keep-parent-{suffix}@demo.com",
            "parent_full_name": "CM Keep Parent",
            "child": {"first_name": "Keep", "last_name": suffix},
            "send_invite": False,
        },
    )
    assert fam.status_code == 201, fam.text
    child_id = fam.json()["childId"]

    db = SessionLocal()
    try:
        from app.models.case import CaseStatus

        case = Case(
            case_code=f"IC-TEST-CM-{suffix}",
            child_id=child_id,
            service_type="Homecare",
            product_module="homecare",
            status=CaseStatus.PENDING_ALLOTMENT,
            case_manager_user_id=other_cm_id,
        )
        db.add(case)
        db.commit()
        db.refresh(case)
        case_id = case.id
    finally:
        db.close()

    assign = client.post(
        f"/api/v1/cases/{case_id}/assignments",
        headers=ah,
        json={
            "therapist_user_id": therapist_id,
            "start_date": "2026-06-01",
            "reason_for_change": "Test assign",
        },
    )
    assert assign.status_code == 201, assign.text

    db = SessionLocal()
    try:
        case = db.get(Case, case_id)
        assert case is not None
        assert case.case_manager_user_id == cm_id
    finally:
        db.close()


def test_admin_profile_patch_syncs_assigned_case_managers():
    suffix = uuid.uuid4().hex[:8]
    admin = _login("superadmin@demo.com")
    ah = _headers(admin)
    target_cm = _get_user_id("casemanager@demo.com")
    other_cm = _get_user_id("shadowcm@demo.com")

    therapists = client.get(
        "/api/v1/admin/allotment/therapists?product_module=homecare&approved_only=false",
        headers=ah,
    ).json()
    therapist_id = therapists[0]["therapist_user_id"]

    db = SessionLocal()
    try:
        profile = db.scalars(
            select(TherapistProfile).where(TherapistProfile.user_id == therapist_id)
        ).first()
        assert profile is not None
        profile_id = profile.id
        profile.supervisor_user_id = other_cm
        db.commit()
    finally:
        db.close()

    fam = client.post(
        "/api/v1/admin/families",
        headers=ah,
        json={
            "parent_email": f"cm-sync-parent-{suffix}@demo.com",
            "parent_full_name": "CM Sync Parent",
            "child": {"first_name": "Sync", "last_name": suffix},
            "send_invite": False,
        },
    )
    assert fam.status_code == 201, fam.text
    child_id = fam.json()["childId"]

    allot = client.post(
        "/api/v1/admin/cases/allot",
        headers=ah,
        json={
            "child_id": child_id,
            "service_type": "Homecare",
            "product_module": "homecare",
            "billing_type": "PER_SESSION",
            "compensation_mode": "PERCENTAGE",
            "client_billing_mode": "POSTPAID",
            "client_rate_per_session_inr": 1200,
            "pay_share_amount_inr": 720,
            "therapist_user_id": therapist_id,
        },
    )
    assert allot.status_code == 201, allot.text
    case_id = allot.json()["case"]["id"]

    db = SessionLocal()
    try:
        case = db.get(Case, case_id)
        assert case is not None
        case.case_manager_user_id = other_cm
        db.commit()
    finally:
        db.close()

    patch = client.patch(
        f"/api/v1/admin/therapist-profiles/{profile_id}",
        headers=ah,
        json={"supervisor_user_id": target_cm},
    )
    assert patch.status_code == 200, patch.text

    db = SessionLocal()
    try:
        case = db.get(Case, case_id)
        profile = db.scalars(
            select(TherapistProfile).where(TherapistProfile.user_id == therapist_id)
        ).first()
        assert profile is not None and profile.supervisor_user_id == target_cm
        assert case is not None and case.case_manager_user_id == target_cm
    finally:
        db.close()


def test_backfill_case_managers_from_therapist_profiles():
    from app.services.assignment_service import backfill_case_managers_from_therapist_profiles

    suffix = uuid.uuid4().hex[:8]
    admin = _login("superadmin@demo.com")
    ah = _headers(admin)
    target_cm = _get_user_id("casemanager@demo.com")
    other_cm = _get_user_id("shadowcm@demo.com")

    therapists = client.get(
        "/api/v1/admin/allotment/therapists?product_module=homecare&approved_only=false",
        headers=ah,
    ).json()
    therapist_id = therapists[0]["therapist_user_id"]

    db = SessionLocal()
    try:
        profile = db.scalars(
            select(TherapistProfile).where(TherapistProfile.user_id == therapist_id)
        ).first()
        assert profile is not None
        profile.supervisor_user_id = target_cm
        db.commit()
    finally:
        db.close()

    fam = client.post(
        "/api/v1/admin/families",
        headers=ah,
        json={
            "parent_email": f"cm-backfill-parent-{suffix}@demo.com",
            "parent_full_name": "CM Backfill Parent",
            "child": {"first_name": "Backfill", "last_name": suffix},
            "send_invite": False,
        },
    )
    assert fam.status_code == 201, fam.text
    child_id = fam.json()["childId"]

    allot = client.post(
        "/api/v1/admin/cases/allot",
        headers=ah,
        json={
            "child_id": child_id,
            "service_type": "Homecare",
            "product_module": "homecare",
            "billing_type": "PER_SESSION",
            "compensation_mode": "PERCENTAGE",
            "client_billing_mode": "POSTPAID",
            "client_rate_per_session_inr": 1200,
            "pay_share_amount_inr": 720,
            "therapist_user_id": therapist_id,
        },
    )
    assert allot.status_code == 201, allot.text
    case_id = allot.json()["case"]["id"]

    db = SessionLocal()
    try:
        case = db.get(Case, case_id)
        assert case is not None
        case.case_manager_user_id = other_cm
        db.commit()
    finally:
        db.close()

    db = SessionLocal()
    try:
        preview = backfill_case_managers_from_therapist_profiles(db, dry_run=True)
        assert preview["cases_updated"] >= 1
        assert any(m["case_id"] == case_id for m in preview["mismatches"])

        applied = backfill_case_managers_from_therapist_profiles(db, dry_run=False)
        assert applied["cases_updated"] >= 1
        db.commit()

        case = db.get(Case, case_id)
        assert case is not None and case.case_manager_user_id == target_cm
    finally:
        db.close()
