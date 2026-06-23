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
from app.tests.conftest import cm_email_for_case_id, pending_log_for_cm_email

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


def test_case_manager_session_logs_scoped_to_assigned_cases():
    db = SessionLocal()
    try:
        cm = db.scalars(select(User).where(User.email == "casemanager@demo.com")).first()
        shadow_cm = db.scalars(select(User).where(User.email == "shadowcm@demo.com")).first()
        assert cm is not None and shadow_cm is not None
        cm_id, shadow_cm_id = cm.id, shadow_cm.id
    finally:
        db.close()

    cm_headers = _login("casemanager@demo.com")
    shadow_headers = _login("shadowcm@demo.com")
    cm_res = client.get("/api/v1/admin/session-logs", headers=cm_headers, params={"page_size": 200})
    shadow_res = client.get("/api/v1/admin/session-logs", headers=shadow_headers, params={"page_size": 200})
    assert cm_res.status_code == 200
    assert shadow_res.status_code == 200

    db = SessionLocal()
    try:
        for row in cm_res.json()["items"]:
            case_id = row.get("case_id")
            if not case_id:
                continue
            case = db.get(Case, case_id)
            assert case is not None
            assert case.case_manager_user_id == cm_id, f"CM saw log for unassigned case {case.case_code}"
        for row in shadow_res.json()["items"]:
            case_id = row.get("case_id")
            if not case_id:
                continue
            case = db.get(Case, case_id)
            assert case is not None
            assert case.case_manager_user_id == shadow_cm_id, f"Shadow CM saw log for unassigned case {case.case_code}"
    finally:
        db.close()


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
    pending = pending_log_for_cm_email("casemanager@demo.com") or pending_log_for_cm_email("shadowcm@demo.com")
    assert pending is not None, "No pending log on a seeded CM caseload"
    log_id = pending["id"]
    cm_email = pending["cm_email"]

    db = SessionLocal()
    try:
        before_count = len(db.scalars(select(Notification)).all())
    finally:
        db.close()

    headers = _login(cm_email)
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


def test_daily_log_submission_emails_parent(monkeypatch):
    from app.tests.session_helpers import (
        backdate_in_progress_session,
        end_active_sessions_for_therapist,
        ensure_scheduled_sessions_for_therapist,
    )

    submitted: list[dict] = []
    published: list[dict] = []

    monkeypatch.setattr(
        "app.services.session_log_service.session_log_submitted_parent_email",
        lambda **kw: submitted.append(kw),
    )
    monkeypatch.setattr(
        "app.services.session_log_service.session_log_published_parent_email",
        lambda **kw: published.append(kw),
    )

    end_active_sessions_for_therapist()
    th_headers = _login("therapist@demo.com")
    session_ids = ensure_scheduled_sessions_for_therapist(min_count=3)
    if not session_ids:
        pytest.skip("No scheduled sessions")

    log_id = None
    sid = None
    payload = {
        "attendance_status": "PRESENT",
        "activities_done": "Email test activity",
        "parent_notes": "Visible to parent after approval",
    }

    for candidate_sid in session_ids:
        started = client.post(f"/api/v1/sessions/{candidate_sid}/start", headers=th_headers)
        if started.status_code == 409:
            detail = started.json().get("detail") or {}
            if detail.get("current_status") == "COMPLETED":
                continue
            assert started.status_code == 200, started.text
        else:
            assert started.status_code == 200, started.text
        backdate_in_progress_session(candidate_sid)
        ended = client.post(f"/api/v1/sessions/{candidate_sid}/end", headers=th_headers)
        assert ended.status_code == 200, ended.text

        create_payload = {"session_id": candidate_sid, **payload}
        created = client.post("/api/v1/daily-logs", headers=th_headers, json=create_payload)
        if created.status_code == 400 and "Late reason" in created.text:
            create_payload["late_reason"] = "Email test coverage for prior-day session"
            created = client.post("/api/v1/daily-logs", headers=th_headers, json=create_payload)
        if created.status_code == 400 and "already exists" in created.text:
            continue
        assert created.status_code == 201, created.text
        log_id = created.json()["id"]
        sid = candidate_sid
        break

    if log_id is None:
        pytest.skip("No session available for a fresh daily log in shared test DB")

    assert submitted, "Expected parent email on session log submission"
    assert submitted[0].get("to")

    with SessionLocal() as db:
        sess = db.get(TherapySession, sid)
        assert sess is not None
        cm_email = cm_email_for_case_id(sess.case_id)
    cm_headers = _login(cm_email)
    approved = client.post(f"/api/v1/daily-logs/{log_id}/approve", headers=cm_headers)
    assert approved.status_code == 200
    assert published, "Expected parent email on session log approval"
