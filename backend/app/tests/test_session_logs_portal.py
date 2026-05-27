from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.models.assignment import CaseAssignment, CaseAssignmentStatus
from app.models.case import Case
from app.models.daily_log import DailyLog, LogApprovalStatus
from app.models.notification import Notification
from app.models.session import Session as TherapySession
from app.models.session import SessionStatus
from app.models.user import User
from app.models.visibility import VisibilityStatus
from app.seed.demo_seed import run as seed_run
from app.core.database import SessionLocal

client = TestClient(app)


def _login(email: str, password: str = "demo123") -> dict:
    res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, res.text
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module", autouse=True)
def _seed():
    seed_run()


def test_therapist_my_cases_only_assigned():
    headers = _login("therapist@demo.com")
    res = client.get("/api/v1/therapist/my-cases", headers=headers)
    assert res.status_code == 200
    body = res.json()
    assert body["total"] >= 1
    for row in body["items"]:
        assert row["case_code"]
        assert row["case_id"]


def test_therapist_cannot_submit_log_for_unassigned_session():
    headers = _login("therapist@demo.com")
    db = SessionLocal()
    try:
        therapist = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
        foreign = db.scalars(
            select(TherapySession).where(TherapySession.therapist_user_id != therapist.id).limit(1)
        ).first()
        if not foreign:
            pytest.skip("No foreign session in seed")
        session_id = foreign.id
    finally:
        db.close()
    res = client.post(
        "/api/v1/therapist/session-logs",
        headers=headers,
        json={
            "session_id": session_id,
            "attendance_status": "PRESENT",
            "session_notes": "Should fail",
        },
    )
    assert res.status_code == 400


def test_admin_session_logs_pending_filter():
    headers = _login("casemanager@demo.com")
    res = client.get("/api/v1/admin/session-logs", headers=headers, params={"status": "pending", "page_size": 20})
    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    for row in data["items"]:
        if row.get("id"):
            assert row["approval_status"] in ("PENDING", LogApprovalStatus.PENDING.value)


def test_submit_log_notifies_case_manager():
    db = SessionLocal()
    try:
        session = db.scalars(
            select(TherapySession)
            .where(TherapySession.status == SessionStatus.COMPLETED)
            .limit(1)
        ).first()
        if not session:
            pytest.skip("No completed session")
        existing = db.scalars(select(DailyLog).where(DailyLog.session_id == session.id)).first()
        if existing:
            db.delete(existing)
            db.commit()
        case = db.get(Case, session.case_id)
        cm_id = case.case_manager_user_id if case else None
        if not cm_id:
            pytest.skip("Case has no CM")
        before = len(
            db.scalars(
                select(Notification).where(
                    Notification.user_id == cm_id,
                    Notification.entity_type == "daily_log",
                )
            ).all()
        )
        session_id = session.id
    finally:
        db.close()

    headers = _login("therapist@demo.com")
    res = client.post(
        "/api/v1/therapist/session-logs",
        headers=headers,
        json={
            "session_id": session_id,
            "attendance_status": "PRESENT",
            "session_notes": "CM notify test",
            "late_reason": "Retroactive test entry",
        },
    )
    assert res.status_code == 201, res.text

    db = SessionLocal()
    try:
        after = len(
            db.scalars(
                select(Notification).where(
                    Notification.user_id == cm_id,
                    Notification.entity_type == "daily_log",
                )
            ).all()
        )
        assert after > before
    finally:
        db.close()


def test_approve_log_notifies_parent():
    db = SessionLocal()
    try:
        log = db.scalars(
            select(DailyLog)
            .join(TherapySession)
            .where(DailyLog.approval_status == LogApprovalStatus.PENDING)
        ).first()
        assert log is not None
        log_id = log.id
        before = db.scalars(select(Notification)).all()
        before_count = len(before)
    finally:
        db.close()

    headers = _login("casemanager@demo.com")
    res = client.post(f"/api/v1/daily-logs/{log_id}/approve", headers=headers)
    assert res.status_code == 200

    db = SessionLocal()
    try:
        log = db.get(DailyLog, log_id)
        assert log.approval_status == LogApprovalStatus.APPROVED
        assert log.visibility_status == VisibilityStatus.APPROVED_FOR_PARENT
        after = db.scalars(select(Notification).order_by(Notification.id.desc())).all()
        assert len(after) >= before_count
    finally:
        db.close()


def test_parent_sees_only_approved_session_logs():
    headers = _login("parent@demo.com")
    res = client.get("/api/v1/parent/session-logs", headers=headers)
    assert res.status_code == 200
    for row in res.json():
        assert row.get("submitted_at")
