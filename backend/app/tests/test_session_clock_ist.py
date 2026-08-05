"""Session start_time/end_time preserve booked slot; clock lives in actual_*."""

from __future__ import annotations

from datetime import date, datetime, time, timezone
from unittest.mock import patch

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.assignment import CaseAssignment, CaseAssignmentStatus
from app.models.session import Session as TherapySession
from app.models.session import SessionMode, SessionStatus
from app.models.user import User
from app.services import session_service
from app.tests.session_helpers import clear_blocking_pending_logs_for_therapist


def test_end_session_preserves_scheduled_slot_times():
    db = SessionLocal()
    try:
        therapist = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
        assignment = db.scalars(
            select(CaseAssignment).where(
                CaseAssignment.therapist_user_id == therapist.id,
                CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
            )
        ).first()
        assert assignment

        checkin_utc = datetime(2026, 6, 8, 9, 30, tzinfo=timezone.utc)
        checkout_utc = datetime(2026, 6, 8, 10, 30, tzinfo=timezone.utc)

        session = TherapySession(
            case_id=assignment.case_id,
            therapist_user_id=therapist.id,
            scheduled_date=date(2026, 6, 8),
            start_time=time(9, 30),
            end_time=time(10, 30),
            mode=SessionMode.HOME,
            status=SessionStatus.IN_PROGRESS,
            actual_start_at=checkin_utc,
        )
        db.add(session)
        db.flush()

        ended = session_service.end_session(db, session, end_at=checkout_utc)
        assert ended.start_time == time(9, 30)
        assert ended.end_time == time(10, 30)
        assert ended.actual_start_at == checkin_utc
        assert ended.actual_end_at == checkout_utc
    finally:
        db.close()


def test_start_session_preserves_scheduled_start_time():
    clear_blocking_pending_logs_for_therapist()
    db = SessionLocal()
    try:
        therapist = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
        assignment = db.scalars(
            select(CaseAssignment).where(
                CaseAssignment.therapist_user_id == therapist.id,
                CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
            )
        ).first()
        assert assignment

        visit_day = date(2026, 6, 8)
        session = TherapySession(
            case_id=assignment.case_id,
            therapist_user_id=therapist.id,
            scheduled_date=visit_day,
            start_time=time(9, 30),
            end_time=time(10, 30),
            mode=SessionMode.HOME,
            status=SessionStatus.SCHEDULED,
        )
        db.add(session)
        db.flush()

        checkin_utc = datetime(2026, 6, 8, 9, 31, tzinfo=timezone.utc)

        with patch.object(session_service, "_now", return_value=checkin_utc):
            with patch.object(session_service, "today_ist", return_value=visit_day):
                with patch("app.services.session_start_service.today_ist", return_value=visit_day):
                    started = session_service.start_session(db, session, therapist.id)

        assert started.start_time == time(9, 30)
        assert started.end_time == time(10, 30)
        assert started.actual_start_at == checkin_utc
    finally:
        db.rollback()
        db.close()
