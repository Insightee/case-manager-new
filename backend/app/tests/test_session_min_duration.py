"""Session minimum duration and product-aware auto-end rules."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

import pytest
from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.session_rules import MIN_SESSION_DURATION_ERROR, validate_session_duration_minutes
from app.models.assignment import CaseAssignment, CaseAssignmentStatus
from app.models.case import Case
from app.models.session import Session as TherapySession
from app.models.session import SessionMode, SessionStatus
from app.models.user import User
from app.services import session_service


def test_validate_session_duration_rejects_under_five_minutes():
    with pytest.raises(ValueError, match="5 minutes"):
        validate_session_duration_minutes(4)


def test_end_session_rejects_short_manual_end():
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
        session = TherapySession(
            case_id=assignment.case_id,
            therapist_user_id=therapist.id,
            scheduled_date=date.today(),
            start_time=time(10, 0),
            mode=SessionMode.HOME,
            status=SessionStatus.IN_PROGRESS,
            actual_start_at=datetime.now(timezone.utc) - timedelta(minutes=3),
        )
        db.add(session)
        db.flush()
        with pytest.raises(ValueError, match=MIN_SESSION_DURATION_ERROR):
            session_service.end_session(db, session)
    finally:
        db.close()


def test_auto_end_homecare_caps_at_three_hours():
    db = SessionLocal()
    try:
        therapist = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
        case = db.scalars(select(Case).where(Case.product_module == "homecare")).first()
        if not case:
            pytest.skip("No homecare case in seed data")
        started = datetime.now(timezone.utc) - timedelta(hours=4)
        session = TherapySession(
            case_id=case.id,
            therapist_user_id=therapist.id,
            scheduled_date=date.today(),
            start_time=time(8, 0),
            mode=SessionMode.HOME,
            status=SessionStatus.IN_PROGRESS,
            actual_start_at=started,
        )
        db.add(session)
        db.flush()
        db.refresh(session, attribute_names=["case"])
        ended = session_service.auto_end_if_stale(db, session)
        assert ended.status == SessionStatus.COMPLETED
        assert ended.auto_ended is True
        assert ended.auto_end_reason == "homecare_3h_limit"
        assert ended.actual_end_at == started + timedelta(hours=3)
    finally:
        db.close()


def test_create_manual_session_rejects_short_duration():
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
        start = datetime.now(timezone.utc) - timedelta(minutes=10)
        end = start + timedelta(minutes=2)
        with pytest.raises(ValueError, match="5 minutes"):
            session_service.create_manual_session(
                db,
                case_id=assignment.case_id,
                therapist_user_id=therapist.id,
                scheduled_date=date.today(),
                actual_start_at=start,
                actual_end_at=end,
                mode=SessionMode.HOME,
            )
    finally:
        db.close()
