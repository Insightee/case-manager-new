from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.database import SessionLocal
from app.main import app
from app.models.assignment import CaseAssignment, CaseAssignmentStatus
from app.models.case import Case
from app.models.therapist_profile import TherapistProfile
from app.models.user import User
from app.services import parent_service
from app.tests.conftest import cm_headers_for_case, login_headers

client = TestClient(app)


def _first_case_with_parent_and_assignment(db):
    cases = db.scalars(select(Case).order_by(Case.id)).all()
    for case in cases:
        parent_id = parent_service.primary_parent_user_id_for_child(db, case.child_id)
        assignment = db.scalars(
            select(CaseAssignment)
            .where(
                CaseAssignment.case_id == case.id,
                CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
            )
            .order_by(CaseAssignment.id.desc())
        ).first()
        if parent_id and assignment:
            return case, parent_id, assignment.therapist_user_id
    raise AssertionError("Expected a seeded case with both parent and active therapist")


def _first_case_for_therapist(db, therapist_email: str) -> Case:
    therapist = db.scalars(select(User).where(User.email == therapist_email)).first()
    assert therapist is not None
    assignment = db.scalars(
        select(CaseAssignment)
        .where(
            CaseAssignment.therapist_user_id == therapist.id,
            CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
        )
        .order_by(CaseAssignment.id.desc())
    ).first()
    assert assignment is not None
    case = db.get(Case, assignment.case_id)
    assert case is not None
    return case


def test_case_get_includes_contacts_for_admin_and_cm():
    with SessionLocal() as db:
        case, parent_id, therapist_user_id = _first_case_with_parent_and_assignment(db)
        parent = db.get(User, parent_id)
        therapist = db.get(User, therapist_user_id)
        assert parent is not None
        assert therapist is not None
        parent.phone = "+91 90000 00001"
        therapist.phone = "+91 90000 00002"
        db.commit()
        case_id = case.id
        parent_expected = {
            "name": parent.full_name,
            "phone": parent.phone,
            "email": parent.email,
        }
        therapist_expected = {
            "name": therapist.full_name,
            "phone": therapist.phone,
            "email": therapist.email,
        }

    for headers in (
        login_headers(client, "superadmin@demo.com"),
        cm_headers_for_case(client, case_id),
    ):
        res = client.get(f"/api/v1/cases/{case_id}", headers=headers)
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["parent_contact"] == parent_expected
        assert body["therapist_contact"] == therapist_expected


def test_mentor_can_list_and_read_meetings_for_mentored_case():
    with SessionLocal() as db:
        mentor = db.scalars(select(User).where(User.email == "shadowcm@demo.com")).first()
        therapist = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
        assert mentor is not None
        assert therapist is not None
        profile = db.scalars(select(TherapistProfile).where(TherapistProfile.user_id == therapist.id)).first()
        assert profile is not None
        profile.mentor_user_id = mentor.id
        case = _first_case_for_therapist(db, therapist.email)
        case.case_manager_user_id = db.scalars(select(User.id).where(User.email == "casemanager@demo.com")).first()
        db.commit()
        case_id = case.id
        mentor_email = mentor.email

    admin_headers = login_headers(client, "superadmin@demo.com")
    created = client.post(
        "/api/v1/meetings",
        headers=admin_headers,
        json={
            "case_id": case_id,
            "scheduled_date": str(date.today()),
            "scheduled_time": "10:00:00",
            "duration_minutes": 30,
            "meeting_type": "PARENT_MEETING",
            "title": "Mentor scope test meeting",
        },
    )
    assert created.status_code == 201, created.text
    meeting = created.json()

    mentor_headers = login_headers(client, mentor_email)
    listed = client.get(f"/api/v1/meetings?case_id={case_id}", headers=mentor_headers)
    assert listed.status_code == 200, listed.text
    assert any(row["id"] == meeting["id"] for row in listed.json())

    detail = client.get(f"/api/v1/meetings/{meeting['id']}", headers=mentor_headers)
    assert detail.status_code == 200, detail.text
    assert detail.json()["case_id"] == case_id

    outsider_case = None
    with SessionLocal() as db:
        for candidate in db.scalars(select(Case).order_by(Case.id)).all():
            if candidate.id != case_id and not parent_service.primary_parent_user_id_for_child(db, candidate.child_id):
                continue
            if candidate.case_manager_user_id != case.case_manager_user_id:
                outsider_case = candidate
                break
    if outsider_case is not None:
        denied = client.get(f"/api/v1/meetings?case_id={outsider_case.id}", headers=mentor_headers)
        assert denied.status_code == 200


def test_therapist_meeting_list_and_detail_hide_cm_notes():
    with SessionLocal() as db:
        case = _first_case_for_therapist(db, "therapist@demo.com")
        db.commit()
        case_id = case.id

    admin_headers = login_headers(client, "superadmin@demo.com")
    meeting_res = client.post(
        "/api/v1/meetings",
        headers=admin_headers,
        json={
            "case_id": case_id,
            "scheduled_date": str(date.today()),
            "scheduled_time": "11:00:00",
            "duration_minutes": 30,
            "meeting_type": "PARENT_MEETING",
            "title": "Therapist notes masking test",
        },
    )
    assert meeting_res.status_code == 201, meeting_res.text
    meeting = meeting_res.json()

    patch_res = client.patch(
        f"/api/v1/meetings/{meeting['id']}",
        headers=admin_headers,
        json={
            "notes_outcome": "Parent aligned with next steps",
            "notes_summary": "Case manager summary should be hidden from therapists",
        },
    )
    assert patch_res.status_code == 200, patch_res.text

    therapist_headers = login_headers(client, "therapist@demo.com")
    listed = client.get(f"/api/v1/meetings?case_id={case_id}", headers=therapist_headers)
    assert listed.status_code == 200, listed.text
    listed_row = next(row for row in listed.json() if row["id"] == meeting["id"])
    assert listed_row["notes_outcome"] is None
    assert listed_row["notes_summary"] is None
    assert listed_row["actions"] == []

    detail = client.get(f"/api/v1/meetings/{meeting['id']}", headers=therapist_headers)
    assert detail.status_code == 200, detail.text
    detail_row = detail.json()
    assert detail_row["notes_outcome"] is None
    assert detail_row["notes_summary"] is None
    assert detail_row["actions"] == []
