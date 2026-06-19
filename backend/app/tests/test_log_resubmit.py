from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.models.daily_log import DailyLog, LogApprovalStatus
from app.models.notification import Notification
from app.models.session import Session as TherapySession
from app.models.session import SessionStatus
from app.tests.session_helpers import (
    backdate_in_progress_session,
    end_active_sessions_for_therapist,
    ensure_scheduled_sessions_for_therapist,
)

client = TestClient(app)


@pytest.fixture(autouse=True)
def _isolate_therapist_sessions():
    end_active_sessions_for_therapist()
    yield
    end_active_sessions_for_therapist()


def _login(email: str, password: str = "demo123"):
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200
    return r.json()["access_token"]


def _complete_session_with_log(headers):
    session_ids = ensure_scheduled_sessions_for_therapist(min_count=1)
    if not session_ids:
        pytest.skip("No scheduled sessions")
    sid = session_ids[0]
    started = client.post(f"/api/v1/sessions/{sid}/start", headers=headers)
    assert started.status_code == 200, started.text
    backdate_in_progress_session(sid)
    end = client.post(f"/api/v1/sessions/{sid}/end", headers=headers)
    assert end.status_code == 200, end.text
    payload = {
        "session_id": sid,
        "attendance_status": "PRESENT",
        "activities_done": "Initial activities note",
    }
    created = client.post("/api/v1/daily-logs", headers=headers, json=payload)
    if created.status_code == 400 and "Late reason" in created.text:
        payload["late_reason"] = "Test log for resubmit coverage"
        created = client.post("/api/v1/daily-logs", headers=headers, json=payload)
    assert created.status_code == 201, created.text
    return created.json()


def _reject_log(log_id: int, comment: str = "Times do not match attendance"):
    cm_headers = {"Authorization": f"Bearer {_login('casemanager@demo.com')}"}
    res = client.post(
        f"/api/v1/daily-logs/{log_id}/reject",
        headers=cm_headers,
        json={"comment": comment},
    )
    assert res.status_code == 200, res.text
    return res.json()


def test_reject_log_notifies_therapist():
    from app.core.database import SessionLocal

    therapist_headers = {"Authorization": f"Bearer {_login('therapist@demo.com')}"}
    log = _complete_session_with_log(therapist_headers)
    therapist_id = None
    db = SessionLocal()
    try:
        row = db.get(DailyLog, log["id"])
        session = db.get(TherapySession, row.session_id)
        therapist_id = session.therapist_user_id
        before = len(
            db.scalars(
                select(Notification).where(
                    Notification.user_id == therapist_id,
                    Notification.entity_type == "daily_log",
                    Notification.entity_id == log["id"],
                )
            ).all()
        )
    finally:
        db.close()

    _reject_log(log["id"], "Please fix the session times and resubmit.")

    db = SessionLocal()
    try:
        after = len(
            db.scalars(
                select(Notification).where(
                    Notification.user_id == therapist_id,
                    Notification.entity_type == "daily_log",
                    Notification.entity_id == log["id"],
                )
            ).all()
        )
        latest = db.scalars(
            select(Notification)
            .where(
                Notification.user_id == therapist_id,
                Notification.entity_type == "daily_log",
                Notification.entity_id == log["id"],
            )
            .order_by(Notification.id.desc())
        ).first()
        assert after > before
        assert latest is not None
        assert "rejected" in latest.title.lower()
        assert "resubmit" in latest.title.lower()
    finally:
        db.close()


def test_rejected_log_can_be_edited_and_resubmitted():
    therapist_headers = {"Authorization": f"Bearer {_login('therapist@demo.com')}"}
    log = _complete_session_with_log(therapist_headers)
    _reject_log(log["id"])

    got = client.get(f"/api/v1/daily-logs/{log['id']}", headers=therapist_headers)
    assert got.status_code == 200
    body = got.json()
    assert body["approval_status"] == "REJECTED"
    assert body["can_resubmit"] is True
    assert body["can_edit"] is True

    patched = client.patch(
        f"/api/v1/daily-logs/{log['id']}",
        headers=therapist_headers,
        json={"activities_done": "Corrected activities after rejection"},
    )
    assert patched.status_code == 200
    assert patched.json()["approval_status"] == "REJECTED"

    resubmitted = client.post(
        f"/api/v1/daily-logs/{log['id']}/resubmit",
        headers=therapist_headers,
        json={"activities_done": "Corrected activities after rejection"},
    )
    assert resubmitted.status_code == 200, resubmitted.text
    data = resubmitted.json()
    assert data["approval_status"] == "PENDING"
    assert data["can_resubmit"] is False
    assert data["review_note"] is None
    assert data["resubmitted_at"] is not None
    assert data["activities_done"] == "Corrected activities after rejection"


def test_pending_log_cannot_use_resubmit_endpoint():
    therapist_headers = {"Authorization": f"Bearer {_login('therapist@demo.com')}"}
    log = _complete_session_with_log(therapist_headers)
    res = client.post(
        f"/api/v1/daily-logs/{log['id']}/resubmit",
        headers=therapist_headers,
        json={"activities_done": "Should fail"},
    )
    assert res.status_code == 400
    assert "rejected" in res.json()["detail"].lower()
