"""Tests for mentor clinical CM parity — write access, roster, meetings."""

from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.database import SessionLocal
from app.main import app
from app.models.assignment import CaseAssignment, CaseAssignmentStatus
from app.models.case import Case
from app.models.case_manager_meeting import MeetingType
from app.models.daily_log import DailyLog, LogApprovalStatus
from app.models.session import Session as TherapySession
from app.models.therapist_profile import TherapistProfile
from app.models.user import User
from app.seed.demo_seed import run as seed_run

client = TestClient(app)


def setup_module():
    seed_run()


def _login(email: str) -> dict[str, str]:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "demo123"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _two_case_managers(db):
    primary = db.scalars(select(User).where(User.email == "casemanager@demo.com")).first()
    mentor = db.scalars(select(User).where(User.email == "shadowcm@demo.com")).first()
    return primary, mentor


def _setup_mentored_case(db):
    primary, mentor = _two_case_managers(db)
    therapist = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
    assert primary and mentor and therapist
    profile = db.scalars(
        select(TherapistProfile).where(TherapistProfile.user_id == therapist.id)
    ).first()
    assert profile
    profile.mentor_user_id = mentor.id
    profile.supervisor_user_id = primary.id
    assignment = db.scalars(
        select(CaseAssignment).where(
            CaseAssignment.therapist_user_id == therapist.id,
            CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
        )
    ).first()
    assert assignment
    case = db.get(Case, assignment.case_id)
    assert case
    case.case_manager_user_id = primary.id
    db.commit()
    return primary, mentor, therapist, case, profile


def test_mentor_can_approve_log_on_mentored_case():
    with SessionLocal() as db:
        _, mentor, _, case, _ = _setup_mentored_case(db)
        log = db.scalars(
            select(DailyLog)
            .join(TherapySession, DailyLog.session_id == TherapySession.id)
            .where(TherapySession.case_id == case.id)
            .limit(1)
        ).first()
        if not log:
            return
        log.approval_status = LogApprovalStatus.PENDING.value
        db.commit()
        log_id = log.id
        mentor_email = mentor.email

    mentor_headers = _login(mentor_email)
    approve = client.post(f"/api/v1/daily-logs/{log_id}/approve", headers=mentor_headers)
    assert approve.status_code == 200
    assert approve.json()["status"] == "approved"


def test_mentor_still_blocked_on_case_billing_fields():
    with SessionLocal() as db:
        _, mentor, _, case, _ = _setup_mentored_case(db)
        case_id = case.id
        mentor_email = mentor.email

    mentor_headers = _login(mentor_email)
    patch = client.patch(
        f"/api/v1/cases/{case_id}",
        headers=mentor_headers,
        json={"region": "mentor-blocked"},
    )
    assert patch.status_code == 403


def test_mentor_can_book_meeting_on_mentored_case():
    with SessionLocal() as db:
        _, mentor, _, case, _ = _setup_mentored_case(db)
        case_id = case.id
        mentor_id = mentor.id
        mentor_email = mentor.email

    mentor_headers = _login(mentor_email)
    bookable = client.get("/api/v1/meetings/bookable-cases", headers=mentor_headers)
    assert bookable.status_code == 200
    ids = {row["id"] for row in bookable.json()}
    assert case_id in ids

    scheduled = date.today() + timedelta(days=14)
    create = client.post(
        "/api/v1/meetings",
        headers=mentor_headers,
        json={
            "case_id": case_id,
            "scheduled_date": scheduled.isoformat(),
            "scheduled_time": "10:00:00",
            "duration_minutes": 30,
            "meeting_type": MeetingType.MENTOR_REVIEW.value,
            "invite_therapist": True,
        },
    )
    assert create.status_code == 201, create.text
    body = create.json()
    assert body["case_id"] == case_id
    assert body["mentor_user_id"] == mentor_id


def test_mentor_can_create_reply_resolve_ticket_on_mentored_case():
    with SessionLocal() as db:
        primary, mentor, therapist, _, profile = _setup_mentored_case(db)
        assignment = db.scalars(
            select(CaseAssignment)
            .join(Case, Case.id == CaseAssignment.case_id)
            .where(
                CaseAssignment.therapist_user_id == therapist.id,
                CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
                Case.product_module == "shadow_support",
            )
        ).first()
        assert assignment, "Expected shadow_support assignment for mentor ticket test"
        case = db.get(Case, assignment.case_id)
        assert case
        case.case_manager_user_id = primary.id
        db.commit()
        case_id = case.id
        mentor_email = mentor.email

    mentor_headers = _login(mentor_email)
    created = client.post(
        "/api/v1/tickets",
        headers=mentor_headers,
        json={
            "case_id": case_id,
            "subject": "Mentor supervision ticket",
            "body": "Follow-up on therapist casework",
            "category": "OTHER",
        },
    )
    assert created.status_code == 201, created.text
    ticket_id = created.json()["id"]

    reply = client.post(
        f"/api/v1/tickets/{ticket_id}/messages",
        headers=mentor_headers,
        json={"body": "Coaching note for therapist"},
    )
    assert reply.status_code == 201, reply.text

    resolved = client.post(
        f"/api/v1/tickets/{ticket_id}/resolve",
        headers=mentor_headers,
        json={"note": "Handled during mentor review"},
    )
    assert resolved.status_code == 200, resolved.text
    assert resolved.json()["status"] in ("RESOLVED", "resolved", "CLOSED", "closed")


def test_mentor_roster_self_service():
    with SessionLocal() as db:
        _, mentor, therapist, _, profile = _setup_mentored_case(db)
        profile.mentor_user_id = None
        db.commit()
        therapist_user_id = therapist.id
        mentor_email = mentor.email

    mentor_headers = _login(mentor_email)
    listed = client.get("/api/v1/admin/mentor/therapists", headers=mentor_headers)
    assert listed.status_code == 200
    assert listed.json()["total"] == 0

    assign = client.post(
        f"/api/v1/admin/mentor/therapists/{therapist_user_id}",
        headers=mentor_headers,
    )
    assert assign.status_code == 200
    assert assign.json()["mentor_user_id"]

    listed2 = client.get("/api/v1/admin/mentor/therapists", headers=mentor_headers)
    assert listed2.json()["total"] == 1

    remove = client.delete(
        f"/api/v1/admin/mentor/therapists/{therapist_user_id}",
        headers=mentor_headers,
    )
    assert remove.status_code == 200
