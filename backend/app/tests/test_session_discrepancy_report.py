"""Integration smoke tests for session discrepancies HR report."""

from __future__ import annotations

from datetime import date, datetime, time, timezone

import pytest
from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.case import Case
from app.models.daily_log import AttendanceStatus, DailyLog, LogApprovalStatus
from app.models.session import Session as TherapySession
from app.models.session import SessionMode, SessionStatus
from app.models.user import User
from app.services.session_discrepancy_report_service import build_session_discrepancies_report


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_build_report_sheets_privacy_and_missing_log(db):
    therapist = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
    case = db.scalars(select(Case).limit(1)).first()
    if not therapist or not case:
        pytest.skip("Seed data missing")

    visit_day = date(2099, 1, 15)
    completed_no_log = TherapySession(
        case_id=case.id,
        therapist_user_id=therapist.id,
        scheduled_date=visit_day,
        start_time=time(10, 0),
        end_time=time(11, 0),
        mode=SessionMode.HOME,
        status=SessionStatus.COMPLETED,
        actual_start_at=datetime(2099, 1, 15, 10, 0, tzinfo=timezone.utc),
        actual_end_at=datetime(2099, 1, 15, 10, 45, tzinfo=timezone.utc),
    )
    db.add(completed_no_log)
    db.flush()

    payload = build_session_discrepancies_report(
        db,
        date_from=visit_day.isoformat(),
        date_to=visit_day.isoformat(),
        case_id=case.id,
    )
    sheets = payload["sheets"]
    assert "Therapists missing logs" in sheets
    assert "Active cases no log in period" in sheets

    silent = sheets["Active cases no log in period"]
    if silent:
        row = silent[0]
        assert "Child Name" not in row
        assert "Parent Name" not in row
        assert "Case ID" in row

    missing_rows = sheets["Therapists missing logs"]
    assert any(r.get("Missing Logs In Period", 0) >= 1 for r in missing_rows)

    db.delete(completed_no_log)
    db.commit()


def test_pending_log_not_on_missing_sheet(db):
    therapist = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
    case = db.scalars(select(Case).limit(1)).first()
    if not therapist or not case:
        pytest.skip("Seed data missing")

    visit_day = date(2099, 1, 16)
    session = TherapySession(
        case_id=case.id,
        therapist_user_id=therapist.id,
        scheduled_date=visit_day,
        start_time=time(9, 0),
        end_time=time(10, 0),
        mode=SessionMode.HOME,
        status=SessionStatus.COMPLETED,
        actual_start_at=datetime(2099, 1, 16, 9, 0, tzinfo=timezone.utc),
        actual_end_at=datetime(2099, 1, 16, 10, 0, tzinfo=timezone.utc),
    )
    db.add(session)
    db.flush()
    log = DailyLog(
        session_id=session.id,
        attendance_status=AttendanceStatus.PRESENT.value,
        submitted_at=datetime.now(timezone.utc),
        approval_status=LogApprovalStatus.PENDING.value,
        late_addition=False,
    )
    db.add(log)
    db.commit()

    payload = build_session_discrepancies_report(
        db,
        date_from=visit_day.isoformat(),
        date_to=visit_day.isoformat(),
        case_id=case.id,
    )
    missing_rows = payload["sheets"]["Therapists missing logs"]
    assert not any(
        r.get("Case ID") == (case.case_code or str(case.id)) and r.get("Missing Logs In Period")
        for r in missing_rows
    )

    db.delete(log)
    db.delete(session)
    db.commit()
