"""Forgot-to-log duplicate session prevention."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.database import SessionLocal
from app.main import app
from app.models.assignment import CaseAssignment, CaseAssignmentStatus
from app.models.daily_log import DailyLog, LogApprovalStatus
from app.models.session import Session as TherapySession
from app.models.session import SessionMode, SessionStatus
from app.models.user import User
from app.seed.demo_seed import run as seed_run
from app.tests.session_helpers import clear_blocking_pending_logs_for_therapist

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    seed_run()
    clear_blocking_pending_logs_for_therapist()


def _login(email: str) -> dict[str, str]:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "demo123"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _active_case_id(db) -> int:
    therapist = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
    assignment = db.scalars(
        select(CaseAssignment).where(
            CaseAssignment.therapist_user_id == therapist.id,
            CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
        )
    ).first()
    assert assignment
    return assignment.case_id


def test_manual_session_blocks_duplicate_same_day():
    headers = _login("therapist@demo.com")
    db = SessionLocal()
    isolated_date = date(2020, 3, 15)
    try:
        case_id = _active_case_id(db)
        therapist = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
        existing = TherapySession(
            case_id=case_id,
            therapist_user_id=therapist.id,
            scheduled_date=isolated_date,
            start_time=time(10, 0),
            end_time=time(11, 0),
            mode=SessionMode.HOME,
            status=SessionStatus.SCHEDULED,
        )
        db.add(existing)
        db.commit()
        session_id = existing.id
    finally:
        db.close()

    start = datetime.combine(isolated_date, time(14, 0), tzinfo=timezone.utc)
    end = start + timedelta(hours=1)
    res = client.post(
        "/api/v1/sessions/manual",
        headers=headers,
        json={
            "case_id": case_id,
            "scheduled_date": isolated_date.isoformat(),
            "actual_start_at": start.isoformat().replace("+00:00", "Z"),
            "actual_end_at": end.isoformat().replace("+00:00", "Z"),
            "mode": "HOME",
        },
    )
    assert res.status_code == 409
    detail = res.json()["detail"]
    assert detail["code"] == "EXISTING_SESSION_FOR_DATE"
    assert detail["existing_session_id"] == session_id
    assert detail["recommended_action"] == "complete_forgotten"


def test_complete_forgotten_on_scheduled_session_then_log():
    headers = _login("therapist@demo.com")
    db = SessionLocal()
    isolated_date = date(2020, 3, 18)
    try:
        case_id = _active_case_id(db)
        therapist = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
        existing = TherapySession(
            case_id=case_id,
            therapist_user_id=therapist.id,
            scheduled_date=isolated_date,
            start_time=time(10, 0),
            end_time=time(11, 0),
            mode=SessionMode.HOME,
            status=SessionStatus.SCHEDULED,
        )
        db.add(existing)
        db.commit()
        session_id = existing.id
    finally:
        db.close()

    start = datetime.combine(isolated_date, time(14, 0), tzinfo=timezone.utc)
    end = start + timedelta(hours=1)
    completed = client.post(
        f"/api/v1/sessions/{session_id}/complete-forgotten",
        headers=headers,
        json={
            "actual_start_at": start.isoformat().replace("+00:00", "Z"),
            "actual_end_at": end.isoformat().replace("+00:00", "Z"),
            "mode": "HOME",
        },
    )
    assert completed.status_code == 200, completed.text
    body = completed.json()
    assert body["status"] == "COMPLETED"
    assert body["actual_start_at"] is not None
    assert body["actual_end_at"] is not None

    log_res = client.post(
        "/api/v1/daily-logs",
        headers=headers,
        json={
            "session_id": session_id,
            "attendance_status": "PRESENT",
            "activities_done": "Retroactive visit logged after schedule",
            "late_reason": "Forgot to clock in on visit day",
        },
    )
    assert log_res.status_code in (200, 201), log_res.text


def test_manual_session_prefers_completed_over_scheduled_same_day():
    headers = _login("therapist@demo.com")
    db = SessionLocal()
    isolated_date = date(2020, 3, 20)
    try:
        case_id = _active_case_id(db)
        therapist = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
        scheduled = TherapySession(
            case_id=case_id,
            therapist_user_id=therapist.id,
            scheduled_date=isolated_date,
            start_time=time(16, 31),
            end_time=time(17, 31),
            mode=SessionMode.HOME,
            status=SessionStatus.SCHEDULED,
        )
        completed = TherapySession(
            case_id=case_id,
            therapist_user_id=therapist.id,
            scheduled_date=isolated_date,
            start_time=time(10, 0),
            end_time=time(11, 0),
            mode=SessionMode.HOME,
            status=SessionStatus.COMPLETED,
            actual_start_at=datetime.combine(isolated_date, time(10, 0), tzinfo=timezone.utc),
            actual_end_at=datetime.combine(isolated_date, time(11, 0), tzinfo=timezone.utc),
        )
        db.add(scheduled)
        db.add(completed)
        db.commit()
        completed_id = completed.id
    finally:
        db.close()

    start = datetime.combine(isolated_date, time(14, 0), tzinfo=timezone.utc)
    end = start + timedelta(hours=1)
    res = client.post(
        "/api/v1/sessions/manual",
        headers=headers,
        json={
            "case_id": case_id,
            "scheduled_date": isolated_date.isoformat(),
            "actual_start_at": start.isoformat().replace("+00:00", "Z"),
            "actual_end_at": end.isoformat().replace("+00:00", "Z"),
            "mode": "HOME",
        },
    )
    assert res.status_code == 409
    detail = res.json()["detail"]
    assert detail["existing_session_id"] == completed_id
    assert detail["session_status"] == "COMPLETED"
    assert detail["recommended_action"] == "edit_log"


def test_manual_session_allows_different_date():
    clear_blocking_pending_logs_for_therapist()
    headers = _login("therapist@demo.com")
    db = SessionLocal()
    past = date(2020, 3, 10)
    other_day = date(2020, 3, 12)
    try:
        case_id = _active_case_id(db)
        therapist = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
        existing = TherapySession(
            case_id=case_id,
            therapist_user_id=therapist.id,
            scheduled_date=past,
            start_time=time(10, 0),
            end_time=time(11, 0),
            mode=SessionMode.HOME,
            status=SessionStatus.COMPLETED,
            actual_start_at=datetime.combine(past, time(10, 0), tzinfo=timezone.utc),
            actual_end_at=datetime.combine(past, time(11, 0), tzinfo=timezone.utc),
        )
        db.add(existing)
        db.flush()
        db.add(
            DailyLog(
                session_id=existing.id,
                attendance_status="PRESENT",
                activities_done="Prior visit logged",
                approval_status=LogApprovalStatus.APPROVED.value,
                submitted_at=datetime.now(timezone.utc),
            )
        )
        db.commit()
    finally:
        db.close()

    start = datetime.combine(other_day, time(14, 0), tzinfo=timezone.utc)
    end = start + timedelta(hours=1)
    res = client.post(
        "/api/v1/sessions/manual",
        headers=headers,
        json={
            "case_id": case_id,
            "scheduled_date": other_day.isoformat(),
            "actual_start_at": start.isoformat().replace("+00:00", "Z"),
            "actual_end_at": end.isoformat().replace("+00:00", "Z"),
            "mode": "HOME",
        },
    )
    assert res.status_code == 201, res.text
