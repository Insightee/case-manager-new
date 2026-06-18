"""Bulk therapist primary CM + active case CM updates from CSV rows."""

from __future__ import annotations

import uuid
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.database import SessionLocal
from app.main import app
from app.models.assignment import CaseAssignment, CaseAssignmentStatus
from app.models.case import Case, CaseStatus
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


def _get_user(email: str) -> User:
    db = SessionLocal()
    try:
        user = db.scalars(select(User).where(User.email == email)).first()
        assert user is not None
        return user
    finally:
        db.close()


def test_bulk_primary_cm_preview_and_apply_updates_profile_and_active_case():
    suffix = uuid.uuid4().hex[:8]
    admin = _login("superadmin@demo.com")
    ah = _headers(admin)
    wrong_cm = _get_user("superadmin@demo.com")
    target_cm = _get_user("casemanager@demo.com")
    therapist = _get_user("therapist@demo.com")

    db = SessionLocal()
    try:
        profile = db.scalars(
            select(TherapistProfile).where(TherapistProfile.user_id == therapist.id)
        ).first()
        assert profile is not None
        profile.supervisor_user_id = wrong_cm.id

        fam = client.post(
            "/api/v1/admin/families",
            headers=ah,
            json={
                "parent_email": f"cm-bulk-parent-{suffix}@demo.com",
                "parent_full_name": "CM Bulk Parent",
                "child": {"first_name": "Bulk", "last_name": suffix},
                "send_invite": False,
            },
        )
        assert fam.status_code == 201, fam.text
        child_id = fam.json()["childId"]

        case = Case(
            case_code=f"IC-CM-BULK-{suffix}",
            child_id=child_id,
            service_type="Homecare",
            product_module="homecare",
            status=CaseStatus.ACTIVE,
            case_manager_user_id=wrong_cm.id,
        )
        db.add(case)
        db.flush()
        db.add(
            CaseAssignment(
                case_id=case.id,
                therapist_user_id=therapist.id,
                start_date=date.today(),
                status=CaseAssignmentStatus.ACTIVE,
            )
        )
        db.commit()
        case_id = case.id
    finally:
        db.close()

    row = {
        "therapist_id": therapist.external_employee_id,
        "email": therapist.email,
        "primary_cm_name": target_cm.full_name,
        "case_manager_email": target_cm.email,
    }

    preview = client.post(
        "/api/v1/admin/therapists/bulk-update-primary-cm",
        headers=ah,
        json={"rows": [row], "apply": False},
    )
    assert preview.status_code == 200, preview.text
    body = preview.json()
    assert body["summary"]["will_update"] == 1
    assert body["results"][0]["status"] == "will_update"
    assert body["results"][0]["cases_updated"] >= 1

    apply = client.post(
        "/api/v1/admin/therapists/bulk-update-primary-cm",
        headers=ah,
        json={"rows": [row], "apply": True},
    )
    assert apply.status_code == 200, apply.text
    applied = apply.json()
    assert applied["summary"]["updated"] == 1

    db = SessionLocal()
    try:
        profile = db.scalars(
            select(TherapistProfile).where(TherapistProfile.user_id == therapist.id)
        ).first()
        case = db.get(Case, case_id)
        assert profile is not None and profile.supervisor_user_id == target_cm.id
        assert case is not None and case.case_manager_user_id == target_cm.id
    finally:
        db.close()


def test_bulk_primary_cm_skips_unchanged_row():
    admin = _login("superadmin@demo.com")
    ah = _headers(admin)
    therapist = _get_user("therapist@demo.com")
    cm = _get_user("casemanager@demo.com")

    db = SessionLocal()
    try:
        profile = db.scalars(
            select(TherapistProfile).where(TherapistProfile.user_id == therapist.id)
        ).first()
        assert profile is not None
        profile.supervisor_user_id = cm.id
        active_case_ids = db.scalars(
            select(Case.id)
            .join(CaseAssignment, CaseAssignment.case_id == Case.id)
            .where(
                CaseAssignment.therapist_user_id == therapist.id,
                CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
                Case.status == CaseStatus.ACTIVE,
            )
        ).all()
        for active_case_id in active_case_ids:
            active_case = db.get(Case, active_case_id)
            if active_case:
                active_case.case_manager_user_id = cm.id
        db.commit()
    finally:
        db.close()

    response = client.post(
        "/api/v1/admin/therapists/bulk-update-primary-cm",
        headers=ah,
        json={
            "rows": [
                {
                    "email": therapist.email,
                    "case_manager_email": cm.email,
                    "primary_cm_name": cm.full_name,
                }
            ],
            "apply": False,
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["summary"]["unchanged"] == 1


def test_bulk_primary_cm_warns_on_primary_cm_name_mismatch():
    admin = _login("superadmin@demo.com")
    ah = _headers(admin)
    therapist = _get_user("therapist@demo.com")
    cm = _get_user("casemanager@demo.com")
    wrong_cm = _get_user("superadmin@demo.com")

    db = SessionLocal()
    try:
        profile = db.scalars(
            select(TherapistProfile).where(TherapistProfile.user_id == therapist.id)
        ).first()
        assert profile is not None
        profile.supervisor_user_id = wrong_cm.id
        db.commit()
    finally:
        db.close()

    response = client.post(
        "/api/v1/admin/therapists/bulk-update-primary-cm",
        headers=ah,
        json={
            "rows": [
                {
                    "email": therapist.email,
                    "case_manager_email": cm.email,
                    "primary_cm_name": "Definitely Not The CM Name",
                }
            ],
            "apply": False,
        },
    )
    assert response.status_code == 200, response.text
    result = response.json()["results"][0]
    assert result["status"] == "will_update"
    assert result["warning"] is not None
