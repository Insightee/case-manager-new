"""Session day-end auto-close, same-day vs stale IN_PROGRESS, idempotent end."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.timezone import IST, ensure_utc_aware, today_ist
from app.main import app
from app.models.assignment import CaseAssignment, CaseAssignmentStatus
from app.models.case import Case
from app.models.session import Session as TherapySession
from app.models.session import SessionMode, SessionStatus
from app.models.user import User
from app.services import session_day_end_service, session_service, therapist_portal_queries as tpq
from app.tests.session_helpers import (
    end_active_sessions_for_therapist,
    ensure_scheduled_sessions_for_therapist,
    utc_started_at_on_session_day,
)

client = TestClient(app)


@pytest.fixture(autouse=True)
def _isolate_sessions():
    end_active_sessions_for_therapist()
    yield
    end_active_sessions_for_therapist()


def _therapist_headers() -> dict:
    r = client.post("/api/v1/auth/login", json={"email": "therapist@demo.com", "password": "demo123"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _create_in_progress(
    db,
    *,
    therapist_id: int,
    case_id: int,
    session_day: date,
    started_at: datetime,
) -> TherapySession:
    session = TherapySession(
        case_id=case_id,
        therapist_user_id=therapist_id,
        scheduled_date=session_day,
        start_time=time(10, 0),
        end_time=time(11, 0),
        mode=SessionMode.HOME,
        status=SessionStatus.IN_PROGRESS,
        actual_start_at=started_at,
    )
    db.add(session)
    db.flush()
    return session


def test_same_day_in_progress_blocks_new_session():
    headers = _therapist_headers()
    today = today_ist()
    db = SessionLocal()
    try:
        therapist = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
        assignments = db.scalars(
            select(CaseAssignment).where(
                CaseAssignment.therapist_user_id == therapist.id,
                CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
            )
        ).all()
        if len(assignments) < 2:
            pytest.skip("Need two active case assignments")
        active_case_id = assignments[0].case_id
        scheduled_case_id = assignments[1].case_id
        _create_in_progress(
            db,
            therapist_id=therapist.id,
            case_id=active_case_id,
            session_day=today,
            started_at=utc_started_at_on_session_day(today, minutes_ago=30),
        )
        scheduled = TherapySession(
            case_id=scheduled_case_id,
            therapist_user_id=therapist.id,
            scheduled_date=today,
            start_time=time(15, 0),
            end_time=time(16, 0),
            mode=SessionMode.HOME,
            status=SessionStatus.SCHEDULED,
        )
        db.add(scheduled)
        db.commit()
        sid = scheduled.id
    finally:
        db.close()
    r = client.post(f"/api/v1/sessions/{sid}/start", headers=headers, json={})
    assert r.status_code == 409, r.text


def test_previous_day_in_progress_does_not_block_today():
    headers = _therapist_headers()
    ids = ensure_scheduled_sessions_for_therapist(min_count=1)
    today = today_ist()
    yesterday = today - timedelta(days=1)
    db = SessionLocal()
    try:
        therapist = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
        case = db.scalars(select(Case).limit(1)).first()
        stale_start = datetime.combine(yesterday, time(15, 0), tzinfo=IST).astimezone(timezone.utc)
        _create_in_progress(db, therapist_id=therapist.id, case_id=case.id, session_day=yesterday, started_at=stale_start)
        db.commit()
        sid = None
        for i in ids:
            s = db.get(TherapySession, i)
            if s and s.scheduled_date == today and s.status == SessionStatus.SCHEDULED:
                sid = i
                break
    finally:
        db.close()
    if not sid:
        pytest.skip("No today scheduled session")
    r = client.post(f"/api/v1/sessions/{sid}/start", headers=headers, json={})
    assert r.status_code == 200, r.text
    ws = client.get("/api/v1/therapist/sessions/workspace", headers=headers)
    assert ws.status_code == 200
    body = ws.json()
    assert body.get("active_session") is not None
    assert len(body.get("stale_previous_sessions") or []) >= 1


def test_auto_close_sessions_at_10pm_ist_today():
    db = SessionLocal()
    try:
        therapist = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
        case = db.scalars(select(Case).limit(1)).first()
        today = today_ist()
        started = datetime.combine(today, time(14, 0), tzinfo=IST).astimezone(timezone.utc)
        session = _create_in_progress(db, therapist_id=therapist.id, case_id=case.id, session_day=today, started_at=started)
        db.commit()
        sid = session.id
        now_ist = datetime.combine(today, time(22, 30), tzinfo=IST)
        closed = session_day_end_service.auto_close_open_sessions_at_day_end(db, now_ist)
        db.commit()
        assert sid in closed
        refreshed = db.get(TherapySession, sid)
        assert refreshed.status == SessionStatus.COMPLETED
        assert refreshed.auto_ended is True
        assert refreshed.auto_end_reason == "day_end_10pm_ist"
        end_ist = ensure_utc_aware(refreshed.actual_end_at).astimezone(IST)
        assert end_ist.date() == today
        assert end_ist.hour == 22
        assert refreshed.daily_log is None
    finally:
        db.close()


def test_auto_close_historical_in_progress_at_10pm():
    db = SessionLocal()
    try:
        therapist = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
        case = db.scalars(select(Case).limit(1)).first()
        today = today_ist()
        old_day = today - timedelta(days=5)
        started = datetime.combine(old_day, time(9, 0), tzinfo=IST).astimezone(timezone.utc)
        session = _create_in_progress(db, therapist_id=therapist.id, case_id=case.id, session_day=old_day, started_at=started)
        db.commit()
        sid = session.id
        now_ist = datetime.combine(today, time(22, 30), tzinfo=IST)
        session_day_end_service.auto_close_open_sessions_at_day_end(db, now_ist)
        db.commit()
        refreshed = db.get(TherapySession, sid)
        assert refreshed.status == SessionStatus.COMPLETED
        assert refreshed.auto_end_reason == "historical_cleanup_at_day_end"
        end_ist = ensure_utc_aware(refreshed.actual_end_at).astimezone(IST)
        assert end_ist.date() == old_day
    finally:
        db.close()


def test_auto_closed_sessions_appear_as_needs_log():
    db = SessionLocal()
    try:
        therapist = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
        case_ids = [c.id for c in db.scalars(select(Case).limit(3)).all()]
        today = today_ist()
        started = datetime.combine(today, time(12, 0), tzinfo=IST).astimezone(timezone.utc)
        session = _create_in_progress(db, therapist_id=therapist.id, case_id=case_ids[0], session_day=today, started_at=started)
        db.commit()
        sid = session.id
        now_ist = datetime.combine(today, time(22, 5), tzinfo=IST)
        session_day_end_service.auto_close_open_sessions_at_day_end(db, now_ist)
        db.commit()
        needs = tpq.fetch_needs_log_sessions(db, therapist, case_ids, limit=50)
        assert any(s.id == sid for s in needs)
    finally:
        db.close()


def test_needs_log_does_not_block_start():
    pytest.skip("Replaced by test_pending_log_gate.test_needs_log_blocks_start")


def test_end_session_idempotent_when_completed():
    headers = _therapist_headers()
    ids = ensure_scheduled_sessions_for_therapist(min_count=1)
    today = today_ist()
    sid = None
    db = SessionLocal()
    try:
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
    from app.tests.session_helpers import backdate_in_progress_session

    backdate_in_progress_session(sid, minutes_ago=6)
    r1 = client.post(f"/api/v1/sessions/{sid}/end", headers=headers, json={})
    assert r1.status_code == 200
    r2 = client.post(f"/api/v1/sessions/{sid}/end", headers=headers, json={})
    assert r2.status_code == 200
    assert r2.json()["status"] == "COMPLETED"


def test_start_session_idempotent_same_session():
    headers = _therapist_headers()
    ids = ensure_scheduled_sessions_for_therapist(min_count=1)
    today = today_ist()
    sid = None
    db = SessionLocal()
    try:
        for i in ids:
            s = db.get(TherapySession, i)
            if s and s.scheduled_date == today:
                sid = i
                break
    finally:
        db.close()
    if not sid:
        pytest.skip("No today session")
    r1 = client.post(f"/api/v1/sessions/{sid}/start", headers=headers, json={})
    r2 = client.post(f"/api/v1/sessions/{sid}/start", headers=headers, json={})
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json()["id"] == r2.json()["id"]
    assert r2.json()["status"] == "IN_PROGRESS"


def test_close_previous_day_open_sessions_skips_same_day():
    db = SessionLocal()
    try:
        therapist = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
        case = db.scalars(select(Case).limit(1)).first()
        today = today_ist()
        yesterday = today - timedelta(days=2)
        stale_start = datetime.combine(yesterday, time(11, 0), tzinfo=IST).astimezone(timezone.utc)
        today_start = datetime.combine(today, time(10, 0), tzinfo=IST).astimezone(timezone.utc)
        stale = _create_in_progress(
            db, therapist_id=therapist.id, case_id=case.id, session_day=yesterday, started_at=stale_start
        )
        live = _create_in_progress(
            db, therapist_id=therapist.id, case_id=case.id, session_day=today, started_at=today_start
        )
        db.commit()
        stale_id, live_id = stale.id, live.id
        now_ist = datetime.combine(today, time(15, 0), tzinfo=IST)
        closed = session_day_end_service.close_previous_day_open_sessions(db, now_ist)
        db.commit()
        assert stale_id in closed
        assert live_id not in closed
        assert db.get(TherapySession, stale_id).status == SessionStatus.COMPLETED
        assert db.get(TherapySession, live_id).status == SessionStatus.IN_PROGRESS
    finally:
        db.close()
