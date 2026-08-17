from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.timezone import today_ist
from app.main import app
from app.models.assignment import CaseAssignment, CaseAssignmentStatus
from app.models.case import Case
from app.models.child import Child
from app.models.daily_log import DailyLog, LogApprovalStatus
from app.models.parent import ParentGuardian
from app.models.session import Session as TherapySession
from app.models.session import SessionStatus
from app.models.user import User
from app.seed.demo_seed import run as seed_run
from app.tests.conftest import cm_headers_for_case

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def _seed():
    seed_run()


def _login(email: str, password: str = "demo123") -> dict:
    res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _create_and_optionally_approve_log(*, approve: bool) -> tuple[int, int]:
    db = SessionLocal()
    try:
        therapist = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
        assignment = db.scalars(
            select(CaseAssignment).where(
                CaseAssignment.therapist_user_id == therapist.id,
                CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
            )
        ).first()
        if not therapist or not assignment:
            pytest.skip("No active therapist assignment in seed")
        now = datetime.now(timezone.utc)
        session = TherapySession(
            case_id=assignment.case_id,
            therapist_user_id=therapist.id,
            scheduled_date=today_ist(),
            status=SessionStatus.COMPLETED,
            actual_start_at=now,
            actual_end_at=now,
            is_additional_visit=True,
        )
        db.add(session)
        db.flush()
        log = DailyLog(
            session_id=session.id,
            attendance_status="PRESENT",
            activities_done="Practised turn-taking with preferred toys.",
            parent_notes="Family update for download test.",
            session_notes="INTERNAL_CLINICAL_SECRET_XYZ",
            observations="Internal observation for staff PDF only.",
            approval_status=LogApprovalStatus.PENDING.value,
            submitted_at=now,
        )
        db.add(log)
        db.commit()
        log_id = log.id
        case_id = assignment.case_id
    finally:
        db.close()

    if approve:
        db = SessionLocal()
        try:
            user = db.scalars(select(User).where(User.email == "casemanager@demo.com")).first()
            case = db.get(Case, case_id)
            case.case_manager_user_id = user.id
            db.commit()
        finally:
            db.close()
        approve_headers = cm_headers_for_case(client, case_id)
        approved = client.post(f"/api/v1/daily-logs/{log_id}/approve", headers=approve_headers)
        assert approved.status_code == 200, approved.text
    return log_id, case_id


def _parent_headers_for_case(case_id: int) -> dict:
    db = SessionLocal()
    try:
        case = db.get(Case, case_id)
        assert case is not None
        parent_user = db.scalars(select(User).where(User.email == "parent@demo.com")).first()
        assert parent_user is not None
        pg = db.scalars(select(ParentGuardian).where(ParentGuardian.user_id == parent_user.id)).first()
        if not pg:
            pg = ParentGuardian(user_id=parent_user.id)
            db.add(pg)
            db.flush()
        child = db.get(Child, case.child_id)
        if child and child not in pg.children:
            pg.children.append(child)
        db.commit()
    finally:
        db.close()
    return _login("parent@demo.com")


def test_therapist_downloads_approved_log_pdf():
    log_id, _case_id = _create_and_optionally_approve_log(approve=True)
    th_headers = _login("therapist@demo.com")
    res = client.get(f"/api/v1/daily-logs/{log_id}/download", headers=th_headers)
    assert res.status_code == 200, res.text
    assert res.headers.get("content-type", "").startswith("application/pdf")
    assert res.content[:4] == b"%PDF"
    assert "attachment;" in (res.headers.get("content-disposition") or "")


def test_therapist_cannot_download_pending_log():
    log_id, _case_id = _create_and_optionally_approve_log(approve=False)
    th_headers = _login("therapist@demo.com")
    res = client.get(f"/api/v1/daily-logs/{log_id}/download", headers=th_headers)
    assert res.status_code == 400
    assert "approved" in res.json()["detail"].lower()


def test_parent_downloads_approved_log_and_not_pending():
    log_id, case_id = _create_and_optionally_approve_log(approve=True)
    parent_h = _parent_headers_for_case(case_id)
    res = client.get(f"/api/v1/parent/session-logs/{log_id}/download", headers=parent_h)
    assert res.status_code == 200, res.text
    assert res.content[:4] == b"%PDF"

    pending_id, pending_case_id = _create_and_optionally_approve_log(approve=False)
    pending_parent = _parent_headers_for_case(pending_case_id)
    denied = client.get(f"/api/v1/parent/session-logs/{pending_id}/download", headers=pending_parent)
    assert denied.status_code == 400


def test_parent_cannot_use_staff_download_route():
    log_id, case_id = _create_and_optionally_approve_log(approve=True)
    parent_h = _parent_headers_for_case(case_id)
    res = client.get(f"/api/v1/daily-logs/{log_id}/download", headers=parent_h)
    assert res.status_code in (403, 404)


def test_missing_log_download_is_not_found():
    th_headers = _login("therapist@demo.com")
    res = client.get("/api/v1/daily-logs/99999999/download", headers=th_headers)
    assert res.status_code == 404
