"""CM mentor: therapist-scoped case visibility + mentor log review."""

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.database import SessionLocal
from app.main import app
from app.models.assignment import CaseAssignment, CaseAssignmentStatus
from app.models.case import Case
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


def test_mentor_must_be_case_manager():
    headers = _login("superadmin@demo.com")
    with SessionLocal() as db:
        therapist = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
        assert therapist
        finance = db.scalars(select(User).where(User.email == "finance@demo.com")).first()
        assert finance
        profile = db.scalars(
            select(TherapistProfile).where(TherapistProfile.user_id == therapist.id)
        ).first()
        assert profile
        profile_id = profile.id
        finance_id = finance.id

    r = client.patch(
        f"/api/v1/admin/therapist-profiles/{profile_id}",
        headers=headers,
        json={"mentor_user_id": finance_id},
    )
    assert r.status_code == 400
    assert "case manager" in r.json()["detail"].lower()


def test_mentor_sees_mentored_therapist_cases_read_only():
    with SessionLocal() as db:
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
        case_id = case.id
        mentor_email = mentor.email

    mentor_headers = _login(mentor_email)
    detail = client.get(f"/api/v1/cases/{case_id}", headers=mentor_headers)
    assert detail.status_code == 200
    body = detail.json()
    assert body["access_as_mentor"] is True

    patch = client.patch(
        f"/api/v1/cases/{case_id}",
        headers=mentor_headers,
        json={"region": "mentor-blocked"},
    )
    assert patch.status_code == 403
    assert "view-only" in patch.json()["detail"].lower() or "Mentor" in patch.json()["detail"]


def test_mentor_can_mark_log_reviewed_without_approving():
    with SessionLocal() as db:
        primary, mentor = _two_case_managers(db)
        therapist = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
        assert primary and mentor and therapist
        profile = db.scalars(
            select(TherapistProfile).where(TherapistProfile.user_id == therapist.id)
        ).first()
        profile.mentor_user_id = mentor.id
        assignment = db.scalars(
            select(CaseAssignment).where(
                CaseAssignment.therapist_user_id == therapist.id,
                CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
            )
        ).first()
        case = db.get(Case, assignment.case_id)
        case.case_manager_user_id = primary.id
        log = db.scalars(
            select(DailyLog)
            .join(TherapySession, DailyLog.session_id == TherapySession.id)
            .where(
                TherapySession.case_id == case.id,
                TherapySession.therapist_user_id == therapist.id,
            )
            .limit(1)
        ).first()
        if not log:
            db.rollback()
            return
        log.approval_status = LogApprovalStatus.PENDING.value
        log.mentor_reviewed_at = None
        log.mentor_reviewed_by_user_id = None
        db.commit()
        log_id = log.id
        mentor_email = mentor.email
        primary_email = primary.email
        therapist_email = therapist.email

    mentor_headers = _login(mentor_email)
    approve = client.post(f"/api/v1/daily-logs/{log_id}/approve", headers=mentor_headers)
    assert approve.status_code == 403

    marked = client.post(f"/api/v1/daily-logs/{log_id}/mentor-review", headers=mentor_headers)
    assert marked.status_code == 200
    assert marked.json()["mentor_reviewed"] is True
    assert marked.json()["approval_status"] == "PENDING"

    again = client.post(f"/api/v1/daily-logs/{log_id}/mentor-review", headers=mentor_headers)
    assert again.status_code == 400

    cm_headers = _login(primary_email)
    cm_log = client.get(f"/api/v1/daily-logs/{log_id}", headers=cm_headers)
    assert cm_log.status_code == 200
    assert cm_log.json()["mentor_reviewed"] is True

    th_headers = _login(therapist_email)
    th_log = client.get(f"/api/v1/daily-logs/{log_id}", headers=th_headers)
    assert th_log.status_code == 200
    assert th_log.json()["mentor_reviewed"] is True
