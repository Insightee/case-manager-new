from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.tests.session_helpers import (
    backdate_in_progress_session,
    demo_parent_case_id,
    end_active_sessions_for_therapist,
    ensure_scheduled_sessions_for_therapist,
)

client = TestClient(app)


@pytest.fixture(autouse=True)
def _isolate_therapist_sessions():
    """Shared CI DB: prior tests may leave IN_PROGRESS sessions or consume seed SCHEDULED slots."""
    end_active_sessions_for_therapist()
    yield
    end_active_sessions_for_therapist()


def _login(email: str, password: str = "demo123"):
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200
    return r.json()["access_token"]


def test_therapist_daily_logs_list_defaults_to_own_logs():
    token = _login("therapist@demo.com")
    headers = {"Authorization": f"Bearer {token}"}
    me = client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200
    uid = me.json()["id"]
    default_list = client.get("/api/v1/daily-logs", headers=headers)
    scoped_list = client.get(f"/api/v1/daily-logs?therapist_user_id={uid}", headers=headers)
    assert default_list.status_code == 200
    assert scoped_list.status_code == 200
    default_ids = {row["id"] for row in default_list.json()}
    scoped_ids = {row["id"] for row in scoped_list.json()}
    assert default_ids == scoped_ids


def test_avatar_upload_and_fetch():
    token = _login("therapist@demo.com")
    headers = {"Authorization": f"Bearer {token}"}
    jpeg = bytes([0xff, 0xd8, 0xff, 0xe0, 0, 0x10, 0x4a, 0x46, 0x49, 0x46, 0, 1, 1, 0, 0, 1, 0, 1, 0, 0, 0xff, 0xd9])
    up = client.post(
        "/api/v1/auth/me/avatar",
        headers=headers,
        files={"file": ("photo.jpg", jpeg, "image/jpeg")},
    )
    assert up.status_code == 200, up.text
    assert up.json()["avatar_url"].startswith("/api/v1/files/avatars/")
    me = client.get("/api/v1/auth/me", headers=headers)
    assert me.json()["avatar_url"]
    av = client.get(me.json()["avatar_url"], headers=headers)
    assert av.status_code == 200
    assert av.headers["content-type"].startswith("image/")


def test_avatar_rejects_oversized():
    token = _login("therapist@demo.com")
    big = b"x" * (1_048_576 + 1)
    r = client.post(
        "/api/v1/auth/me/avatar",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("a.jpg", big, "image/jpeg")},
    )
    assert r.status_code == 400


def test_session_start_end_and_log():
    token = _login("therapist@demo.com")
    headers = {"Authorization": f"Bearer {token}"}
    session_ids = ensure_scheduled_sessions_for_therapist(min_count=1)
    if not session_ids:
        pytest.skip("No scheduled sessions available for therapist")
    sid = session_ids[0]
    start = client.post(f"/api/v1/sessions/{sid}/start", headers=headers)
    assert start.status_code == 200
    assert start.json()["status"] == "IN_PROGRESS"
    backdate_in_progress_session(sid)
    active = client.get("/api/v1/sessions/active", headers=headers)
    assert active.status_code == 200
    assert active.json()["id"] == sid
    end = client.post(f"/api/v1/sessions/{sid}/end", headers=headers)
    assert end.status_code == 200
    assert end.json()["status"] == "COMPLETED"
    log = client.post(
        "/api/v1/daily-logs",
        headers=headers,
        json={
            "session_id": sid,
            "attendance_status": "PRESENT",
            "activities_done": "Play therapy",
            "goals_addressed": "Communication",
            "parent_notes": "Good session",
        },
    )
    assert log.status_code == 201
    assert log.json()["goals_addressed"] == "Communication"


def test_parent_session_logs_omit_internal_fields():
    from sqlalchemy import select

    from app.core.database import SessionLocal
    from app.core.timezone import today_ist
    from app.models.daily_log import DailyLog
    from app.models.session import Session as TherapySession
    from app.models.session import SessionStatus

    therapist_token = _login("therapist@demo.com")
    th = {"Authorization": f"Bearer {therapist_token}"}
    parent_case_id = demo_parent_case_id()
    if not parent_case_id:
        pytest.skip("Demo parent case not found")

    sid = None
    existing_log_id = None
    db = SessionLocal()
    try:
        today = today_ist()
        completed = db.scalars(
            select(TherapySession)
            .where(
                TherapySession.case_id == parent_case_id,
                TherapySession.scheduled_date == today,
                TherapySession.status == SessionStatus.COMPLETED,
            )
            .order_by(TherapySession.id.desc())
        ).first()
        if completed:
            sid = completed.id
            existing_log = db.scalars(select(DailyLog).where(DailyLog.session_id == sid)).first()
            if existing_log:
                existing_log_id = existing_log.id
    finally:
        db.close()

    if sid is None:
        session_ids = ensure_scheduled_sessions_for_therapist(
            min_count=1,
            preferred_case_id=parent_case_id,
        )
        if not session_ids:
            pytest.skip("No scheduled sessions")
        sid = session_ids[0]
        started = client.post(f"/api/v1/sessions/{sid}/start", headers=th)
        if started.status_code == 409:
            detail = started.json().get("detail") or {}
            existing_id = detail.get("existing_session_id")
            if existing_id and detail.get("current_status") == "COMPLETED":
                sid = existing_id
            else:
                pytest.skip("No startable session on parent case today")
        else:
            assert started.status_code == 200, started.text
            backdate_in_progress_session(sid)
            ended = client.post(f"/api/v1/sessions/{sid}/end", headers=th)
            assert ended.status_code == 200, ended.text

    log_payload = {
        "attendance_status": "PRESENT",
        "session_notes": "internal only",
        "observations": "clinical internal",
        "parent_notes": "profile-parent-visible-notes",
    }
    if existing_log_id:
        updated = client.patch(
            f"/api/v1/daily-logs/{existing_log_id}",
            headers=th,
            json=log_payload,
        )
        assert updated.status_code == 200, updated.text
        log_id = existing_log_id
    else:
        created = client.post(
            "/api/v1/daily-logs",
            headers=th,
            json={"session_id": sid, **log_payload},
        )
        assert created.status_code == 201, created.text
        log_id = created.json()["id"]
    mgr_token = _login("superadmin@demo.com")
    approve = client.post(f"/api/v1/daily-logs/{log_id}/approve", headers={"Authorization": f"Bearer {mgr_token}"})
    assert approve.status_code == 200, approve.text
    parent_token = _login("parent@demo.com")
    pr = client.get(
        "/api/v1/parent/session-logs",
        headers={"Authorization": f"Bearer {parent_token}"},
        params={"case_id": parent_case_id},
    )
    assert pr.status_code == 200
    rows = pr.json()
    row = next((r for r in rows if r.get("parent_notes") == "profile-parent-visible-notes"), None)
    assert row is not None, "Approved log with parent_notes should appear for parent"
    assert "observations" not in row
    assert "session_notes" not in row


def test_cannot_start_two_sessions():
    token = _login("therapist@demo.com")
    headers = {"Authorization": f"Bearer {token}"}
    session_ids = ensure_scheduled_sessions_for_therapist(min_count=2)
    if len(session_ids) < 2:
        pytest.skip("Need two scheduled sessions")
    s1, s2 = session_ids[0], session_ids[1]
    from app.core.database import SessionLocal
    from app.core.timezone import today_ist
    from app.models.session import Session as TherapySession

    db = SessionLocal()
    try:
        for sid in (s1, s2):
            row = db.get(TherapySession, sid)
            if not row or row.scheduled_date != today_ist():
                pytest.skip("Need two sessions scheduled for today (IST)")
    finally:
        db.close()
    assert client.post(f"/api/v1/sessions/{s1}/start", headers=headers).status_code == 200
    second = client.post(f"/api/v1/sessions/{s2}/start", headers=headers)
    assert second.status_code == 409
    body = second.json()
    assert body.get("detail", {}).get("existing_session_id") == s1
    assert body.get("detail", {}).get("recommended_action") == "CONTINUE_SESSION"
    backdate_in_progress_session(s1)
    client.post(f"/api/v1/sessions/{s1}/end", headers=headers)


def test_case_session_logs_pdf_export():
    token = _login("therapist@demo.com")
    headers = {"Authorization": f"Bearer {token}"}
    case_id = demo_parent_case_id()
    r = client.get(
        f"/api/v1/cases/{case_id}/session-logs/export/pdf?month=2026-01",
        headers=headers,
    )
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/pdf"
    assert r.content[:4] == b"%PDF"


def test_case_session_logs_pdf_includes_all_month_sessions():
    from app.services import case_session_logs_pdf_service as pdf_svc
    from app.core.database import SessionLocal
    from app.models.user import User

    token = _login("therapist@demo.com")
    headers = {"Authorization": f"Bearer {token}"}
    me = client.get("/api/v1/auth/me", headers=headers).json()
    case_id = demo_parent_case_id()

    db = SessionLocal()
    try:
        user = db.get(User, me["id"])
        _, sessions, _, _ = pdf_svc.list_case_sessions_for_log_pdf(
            db, user, case_id=case_id, month="2026-06"
        )
        assert len(sessions) >= 1
        pdf_bytes = pdf_svc.build_case_session_logs_pdf(db, user, case_id=case_id, month="2026-06")
    finally:
        db.close()

    assert pdf_bytes[:4] == b"%PDF"
    assert len(pdf_bytes) > 500
