"""Forgot-to-log duplicate session prevention."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.database import SessionLocal
from app.main import app
from app.models.assignment import CaseAssignment, CaseAssignmentStatus
from app.models.session import Session as TherapySession
from app.models.session import SessionMode, SessionStatus
from app.models.user import User
from app.seed.demo_seed import run as seed_run

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    seed_run()


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
    assert detail["recommended_action"] in {"resume_session", "edit_log", "view_log"}


def test_manual_session_allows_different_date():
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
