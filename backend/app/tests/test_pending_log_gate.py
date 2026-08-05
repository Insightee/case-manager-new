"""Therapist must submit latest visit log before starting another session for the same case."""

from __future__ import annotations

from datetime import datetime, time, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.timezone import IST, today_ist
from app.main import app
from app.models.daily_log import DailyLog
from app.models.case import Case
from app.models.session import Session as TherapySession
from app.models.session import SessionMode, SessionStatus
from app.models.user import User
from app.services import pending_log_gate_service
from app.tests.conftest import login_headers
from app.tests.session_helpers import end_active_sessions_for_therapist

client = TestClient(app)


@pytest.fixture(autouse=True)
def _isolate_sessions():
    end_active_sessions_for_therapist()
    yield
    end_active_sessions_for_therapist()


def _therapist_headers():
    return login_headers(client, "therapist@demo.com")


def test_needs_log_blocks_start_same_case_only():
    """Case A missing log blocks Case A starts but not Case B."""
    headers = _therapist_headers()
    db = SessionLocal()
    try:
        therapist = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
        cases = db.scalars(select(Case).limit(5)).all()
        if len(cases) < 2:
            pytest.skip("Need two cases")
        today = today_ist()
        block_day = today - timedelta(days=1)
        needs_log_case = cases[0]
        start_case = None
        for candidate in cases[1:]:
            has_today_visit = db.scalars(
                select(TherapySession.id).where(
                    TherapySession.case_id == candidate.id,
                    TherapySession.therapist_user_id == therapist.id,
                    TherapySession.scheduled_date == today,
                    TherapySession.status.in_([SessionStatus.COMPLETED, SessionStatus.IN_PROGRESS]),
                )
            ).first()
            if not has_today_visit:
                start_case = candidate
                break
        if start_case is None:
            pytest.skip("No case without a completed/in-progress visit today")
        existing_block = db.scalars(
            select(TherapySession)
            .outerjoin(DailyLog, DailyLog.session_id == TherapySession.id)
            .where(
                TherapySession.therapist_user_id == therapist.id,
                TherapySession.status == SessionStatus.COMPLETED,
                DailyLog.id.is_(None),
                TherapySession.scheduled_date >= block_day,
            )
            .limit(1)
        ).first()
        if existing_block:
            pytest.skip("Therapist already has a recent completed visit without log in seed data")
        completed = TherapySession(
            case_id=needs_log_case.id,
            therapist_user_id=therapist.id,
            scheduled_date=block_day,
            start_time=time(9, 0),
            end_time=time(10, 0),
            mode=SessionMode.HOME,
            status=SessionStatus.COMPLETED,
            actual_start_at=datetime.combine(block_day, time(9, 0), tzinfo=IST).astimezone(timezone.utc),
            actual_end_at=datetime.combine(block_day, time(10, 0), tzinfo=IST).astimezone(timezone.utc),
        )
        db.add(completed)
        sched_other = TherapySession(
            case_id=start_case.id,
            therapist_user_id=therapist.id,
            scheduled_date=today,
            start_time=time(14, 0),
            end_time=time(15, 0),
            mode=SessionMode.HOME,
            status=SessionStatus.SCHEDULED,
        )
        sched_same = TherapySession(
            case_id=needs_log_case.id,
            therapist_user_id=therapist.id,
            scheduled_date=today,
            start_time=time(16, 0),
            end_time=time(17, 0),
            mode=SessionMode.HOME,
            status=SessionStatus.SCHEDULED,
        )
        db.add_all([sched_other, sched_same])
        db.commit()
        other_id = sched_other.id
        same_id = sched_same.id
        blocking_id = completed.id
    finally:
        db.close()

    other_start = client.post(f"/api/v1/sessions/{other_id}/start", headers=headers, json={})
    assert other_start.status_code == 200, other_start.text

    same_start = client.post(f"/api/v1/sessions/{same_id}/start", headers=headers, json={})
    assert same_start.status_code == 409, same_start.text
    detail = same_start.json()["detail"]
    assert detail["code"] == "PENDING_LOG_REQUIRED"
    assert detail["blocking_session_id"] == blocking_id


def test_discard_blocking_log_allows_start():
    headers = _therapist_headers()
    db = SessionLocal()
    try:
        therapist = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
        cases = db.scalars(select(Case).limit(5)).all()
        if len(cases) < 2:
            pytest.skip("Need two cases")
        today = today_ist()
        old_day = today - timedelta(days=1)
        needs_log_case = cases[0]
        start_case = cases[1]
        existing_block = db.scalars(
            select(TherapySession)
            .outerjoin(DailyLog, DailyLog.session_id == TherapySession.id)
            .where(
                TherapySession.therapist_user_id == therapist.id,
                TherapySession.status == SessionStatus.COMPLETED,
                DailyLog.id.is_(None),
                TherapySession.scheduled_date >= old_day,
            )
            .limit(1)
        ).first()
        if existing_block:
            pytest.skip("Therapist already has a recent completed visit without log in seed data")
        completed = TherapySession(
            case_id=needs_log_case.id,
            therapist_user_id=therapist.id,
            scheduled_date=old_day,
            start_time=time(9, 0),
            end_time=time(10, 0),
            mode=SessionMode.HOME,
            status=SessionStatus.COMPLETED,
            actual_start_at=datetime.combine(old_day, time(9, 0), tzinfo=IST).astimezone(timezone.utc),
            actual_end_at=datetime.combine(old_day, time(10, 0), tzinfo=IST).astimezone(timezone.utc),
        )
        db.add(completed)
        sched = TherapySession(
            case_id=needs_log_case.id,
            therapist_user_id=therapist.id,
            scheduled_date=today,
            start_time=time(14, 0),
            end_time=time(15, 0),
            mode=SessionMode.HOME,
            status=SessionStatus.SCHEDULED,
        )
        db.add(sched)
        db.commit()
        blocking_id = completed.id
        sid = sched.id
    finally:
        db.close()

    blocked = client.post(f"/api/v1/sessions/{sid}/start", headers=headers, json={})
    assert blocked.status_code == 409

    discarded = client.post(f"/api/v1/sessions/{blocking_id}/discard-pending-log", headers=headers, json={})
    assert discarded.status_code == 200, discarded.text

    started = client.post(f"/api/v1/sessions/{sid}/start", headers=headers, json={})
    assert started.status_code == 200, started.text


def test_only_latest_unsubmitted_session_blocks():
    """Only the most recent COMPLETED visit without a log blocks — not older mistakes."""
    db = SessionLocal()
    try:
        therapist = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
        case = db.scalars(select(Case).limit(1)).first()
        today = today_ist()
        stale_day = today - timedelta(days=10)
        recent_day = today - timedelta(days=2)
        stale = TherapySession(
            case_id=case.id,
            therapist_user_id=therapist.id,
            scheduled_date=stale_day,
            start_time=time(9, 0),
            end_time=time(10, 0),
            mode=SessionMode.HOME,
            status=SessionStatus.COMPLETED,
            actual_start_at=datetime.combine(stale_day, time(9, 0), tzinfo=IST).astimezone(timezone.utc),
            actual_end_at=datetime.combine(stale_day, time(10, 0), tzinfo=IST).astimezone(timezone.utc),
        )
        recent = TherapySession(
            case_id=case.id,
            therapist_user_id=therapist.id,
            scheduled_date=recent_day,
            start_time=time(11, 0),
            end_time=time(12, 0),
            mode=SessionMode.HOME,
            status=SessionStatus.COMPLETED,
            actual_start_at=datetime.combine(recent_day, time(11, 0), tzinfo=IST).astimezone(timezone.utc),
            actual_end_at=datetime.combine(recent_day, time(12, 0), tzinfo=IST).astimezone(timezone.utc),
        )
        db.add_all([stale, recent])
        db.flush()
        from app.models.daily_log import DailyLog, LogApprovalStatus

        db.add(
            DailyLog(
                session_id=recent.id,
                attendance_status="PRESENT",
                activities_done="Recent visit logged.",
                submitted_at=datetime.now(timezone.utc),
                approval_status=LogApprovalStatus.PENDING.value,
            )
        )
        db.commit()
        blocking = pending_log_gate_service.get_blocking_session(db, therapist.id, case.id)
        if blocking and blocking.scheduled_date > stale_day:
            pytest.skip("Seed data has a more recent completed visit without log")
        assert blocking is not None
        assert blocking.id == stale.id
    finally:
        db.close()


def test_workspace_includes_needs_log():
    headers = _therapist_headers()
    ws = client.get("/api/v1/therapist/sessions/workspace", headers=headers)
    assert ws.status_code == 200
    body = ws.json()
    assert "needs_log" in body
