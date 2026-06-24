"""Session start integrity: IST date guard, idempotency, conflict resolution."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.timezone import today_ist
from app.main import app
from app.models.case import Case
from app.models.session import Session as TherapySession
from app.models.session import SessionMode, SessionStatus
from app.models.user import User
from app.services import session_service
from app.tests.session_helpers import end_active_sessions_for_therapist, ensure_scheduled_sessions_for_therapist

client = TestClient(app)


@pytest.fixture(autouse=True)
def _isolate_sessions():
    end_active_sessions_for_therapist()
    yield
    end_active_sessions_for_therapist()


def _therapist_headers() -> dict:
    r = client.post(
        "/api/v1/auth/login",
        json={"email": "therapist@demo.com", "password": "demo123"},
    )
    assert r.status_code == 200
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_start_blocks_future_scheduled_date():
    headers = _therapist_headers()
    db = SessionLocal()
    try:
        therapist = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
        case = db.scalars(select(Case).limit(1)).first()
        future = today_ist() + timedelta(days=3)
        sess = TherapySession(
            case_id=case.id,
            therapist_user_id=therapist.id,
            scheduled_date=future,
            start_time=time(10, 0),
            end_time=time(11, 0),
            mode=SessionMode.HOME,
            status=SessionStatus.SCHEDULED,
        )
        db.add(sess)
        db.commit()
        db.refresh(sess)
        sid = sess.id
    finally:
        db.close()

    r = client.post(f"/api/v1/sessions/{sid}/start", headers=headers, json={})
    assert r.status_code == 400
    detail = r.json()["detail"].lower()
    assert "scheduled visit date" in detail or "forgot" in detail


def test_idempotency_key_returns_same_started_session():
    headers = _therapist_headers()
    ids = ensure_scheduled_sessions_for_therapist(min_count=1)
    today_ids = []
    db = SessionLocal()
    try:
        today = today_ist()
        for sid in ids:
            s = db.get(TherapySession, sid)
            if s and s.scheduled_date == today:
                today_ids.append(sid)
    finally:
        db.close()
    if not today_ids:
        pytest.skip("No scheduled session for today in seed")
    sid = today_ids[0]
    key = f"test-idem-{sid}-{today_ist().isoformat()}"
    headers_with_key = {**headers, "Idempotency-Key": key}

    r1 = client.post(f"/api/v1/sessions/{sid}/start", headers=headers_with_key, json={})
    assert r1.status_code == 200
    r2 = client.post(f"/api/v1/sessions/{sid}/start", headers=headers_with_key, json={})
    assert r2.status_code == 200
    assert r1.json()["id"] == r2.json()["id"]
    assert r2.json()["status"] == "IN_PROGRESS"


def test_continue_in_progress_returns_same_session():
    headers = _therapist_headers()
    ids = ensure_scheduled_sessions_for_therapist(min_count=1)
    db = SessionLocal()
    try:
        today = today_ist()
        sid = None
        for i in ids:
            s = db.get(TherapySession, i)
            if s and s.scheduled_date == today:
                sid = i
                break
    finally:
        db.close()
    if not sid:
        pytest.skip("No today session")
    client.post(f"/api/v1/sessions/{sid}/start", headers=headers, json={})
    r = client.post(f"/api/v1/sessions/{sid}/start", headers=headers, json={})
    assert r.status_code == 200
    assert r.json()["status"] == "IN_PROGRESS"
    assert r.json().get("resumed_count", 0) >= 1


def test_schedule_aware_auto_end_overage(monkeypatch):
    from app.core.timezone import IST

    db = SessionLocal()
    try:
        therapist = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
        case = db.scalars(select(Case).where(Case.product_module == "homecare")).first()
        if not case:
            pytest.skip("No homecare case")
        today = today_ist()
        started = datetime.combine(today, time(15, 0), tzinfo=IST).astimezone(timezone.utc)
        session = TherapySession(
            case_id=case.id,
            therapist_user_id=therapist.id,
            scheduled_date=today,
            start_time=time(15, 0),
            end_time=time(16, 0),
            slot_duration_minutes=60,
            mode=SessionMode.HOME,
            status=SessionStatus.IN_PROGRESS,
            actual_start_at=started,
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        fake_now = datetime.combine(today, time(17, 30), tzinfo=IST).astimezone(timezone.utc)
        monkeypatch.setattr(session_service, "_now", lambda: fake_now)
        ended = session_service.auto_end_if_stale(db, session)
        assert ended.status == SessionStatus.COMPLETED
        assert ended.auto_ended is True
        assert ended.scheduled_duration_mins == 60
        assert ended.overage_mins == 45
        assert ended.time_confirmation_required is True
    finally:
        db.close()


def test_start_blocks_past_scheduled_date():
    headers = _therapist_headers()
    db = SessionLocal()
    try:
        therapist = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
        case = db.scalars(select(Case).limit(1)).first()
        past = today_ist() - timedelta(days=2)
        sess = TherapySession(
            case_id=case.id,
            therapist_user_id=therapist.id,
            scheduled_date=past,
            start_time=time(10, 0),
            end_time=time(11, 0),
            mode=SessionMode.HOME,
            status=SessionStatus.SCHEDULED,
        )
        db.add(sess)
        db.commit()
        db.refresh(sess)
        sid = sess.id
    finally:
        db.close()

    r = client.post(f"/api/v1/sessions/{sid}/start", headers=headers, json={})
    assert r.status_code == 400
    assert "forgot" in r.json()["detail"].lower()


def test_same_day_duplicate_requires_confirmation():
    headers = _therapist_headers()
    db = SessionLocal()
    try:
        from app.models.daily_log import DailyLog

        therapist = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
        case = db.scalars(select(Case).limit(1)).first()
        today = today_ist()
        existing_today = db.scalars(
            select(TherapySession).where(
                TherapySession.case_id == case.id,
                TherapySession.therapist_user_id == therapist.id,
                TherapySession.scheduled_date == today,
            )
        ).all()
        for old in existing_today:
            log = db.scalars(select(DailyLog).where(DailyLog.session_id == old.id)).first()
            if log:
                db.delete(log)
            if old.status == SessionStatus.IN_PROGRESS:
                session_service.end_session(db, old)
            old.status = SessionStatus.CANCELLED
        db.commit()

        first = TherapySession(
            case_id=case.id,
            therapist_user_id=therapist.id,
            scheduled_date=today,
            start_time=time(9, 0),
            end_time=time(10, 0),
            mode=SessionMode.HOME,
            status=SessionStatus.SCHEDULED,
        )
        second = TherapySession(
            case_id=case.id,
            therapist_user_id=therapist.id,
            scheduled_date=today,
            start_time=time(14, 0),
            end_time=time(15, 0),
            mode=SessionMode.HOME,
            status=SessionStatus.SCHEDULED,
        )
        db.add_all([first, second])
        db.commit()
        db.refresh(first)
        db.refresh(second)
        first_id, second_id = first.id, second.id
    finally:
        db.close()

    from app.tests.session_helpers import backdate_in_progress_session

    r1 = client.post(f"/api/v1/sessions/{first_id}/start", headers=headers, json={})
    assert r1.status_code == 200
    backdate_in_progress_session(first_id, minutes_ago=10)
    end_first = client.post(f"/api/v1/sessions/{first_id}/end", headers=headers, json={})
    assert end_first.status_code == 200, end_first.text

    blocked = client.post(f"/api/v1/sessions/{second_id}/start", headers=headers, json={})
    assert blocked.status_code == 409
    detail = blocked.json()["detail"]
    assert detail["recommended_action"] == "DUPLICATE_SAME_DAY"
    assert detail["existing_session_id"] == first_id

    allowed = client.post(
        f"/api/v1/sessions/{second_id}/start",
        headers=headers,
        json={"allow_duplicate": True},
    )
    assert allowed.status_code == 200
    assert allowed.json()["duplicate_day_session"] is True


def test_patch_actual_times_marks_edited_and_re_pends_log():
    from app.tests.session_helpers import backdate_in_progress_session

    headers = _therapist_headers()
    ids = ensure_scheduled_sessions_for_therapist(min_count=1)
    db = SessionLocal()
    try:
        today = today_ist()
        sid = None
        for i in ids:
            s = db.get(TherapySession, i)
            if s and s.scheduled_date == today:
                sid = i
                break
    finally:
        db.close()
    if not sid:
        pytest.skip("No today session")

    assert client.post(f"/api/v1/sessions/{sid}/start", headers=headers, json={}).status_code == 200
    backdate_in_progress_session(sid, minutes_ago=30)
    assert client.post(f"/api/v1/sessions/{sid}/end", headers=headers, json={}).status_code == 200

    log_payload = {
        "session_id": sid,
        "attendance_status": "PRESENT",
        "activities_done": "Coverage for actual-times edit",
    }
    created = client.post("/api/v1/daily-logs", headers=headers, json=log_payload)
    if created.status_code == 400 and "Late reason" in created.text:
        log_payload["late_reason"] = "Test late log"
        created = client.post("/api/v1/daily-logs", headers=headers, json=log_payload)
    assert created.status_code == 201, created.text
    log_id = created.json()["id"]

    ended = client.get(f"/api/v1/sessions/{sid}", headers=headers).json()
    start_at = ended["actual_start_at"]
    end_at = ended["actual_end_at"]
    from datetime import datetime as dt

    new_start = dt.fromisoformat(start_at.replace("Z", "+00:00")) - timedelta(minutes=5)
    new_end = dt.fromisoformat(end_at.replace("Z", "+00:00")) - timedelta(minutes=5)

    patched = client.patch(
        f"/api/v1/sessions/{sid}/actual-times",
        headers=headers,
        json={
            "actual_start_at": new_start.isoformat().replace("+00:00", "Z"),
            "actual_end_at": new_end.isoformat().replace("+00:00", "Z"),
            "edit_reason": "Corrected mistaken clock-out time",
        },
    )
    assert patched.status_code == 200, patched.text
    body = patched.json()
    assert body["actual_times_edited"] is True
    assert body["actual_start_at"] == start_at
    assert body["actual_end_at"] == end_at
    assert body["edited_start_at"] is not None
    assert body["edited_end_at"] is not None

    log_read = client.get(f"/api/v1/daily-logs/{log_id}", headers=headers).json()
    assert log_read["approval_status"] == "PENDING"
    assert log_read["edited_start_at"] is not None
    assert log_read["edited_end_at"] is not None
