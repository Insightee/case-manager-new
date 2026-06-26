"""Void completed sessions before log submission."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.core.timezone import today_ist
from app.models.audit_event import AuditEvent
from app.models.assignment import CaseAssignment, CaseAssignmentStatus
from app.models.session import Session as TherapySession
from app.models.session import SessionMode, SessionStatus
from app.models.slot import SlotStatus, TherapistSlot
from app.models.user import User
from app.services import session_service
from app.core.database import SessionLocal

IST = ZoneInfo("Asia/Kolkata")


def _therapist_and_case(db):
    therapist = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
    assignment = db.scalars(
        select(CaseAssignment).where(
            CaseAssignment.therapist_user_id == therapist.id,
            CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
        )
    ).first()
    assert therapist and assignment
    return therapist, assignment.case_id


def _completed_session(
    db,
    *,
    therapist_id: int,
    case_id: int,
    started_hours_ago: float = 1.0,
    slot_id: int | None = None,
):
    started = datetime.now(timezone.utc) - timedelta(hours=started_hours_ago)
    ended = started + timedelta(minutes=45)
    session = TherapySession(
        case_id=case_id,
        therapist_user_id=therapist_id,
        scheduled_date=today_ist(),
        start_time=time(10, 0),
        end_time=time(11, 0),
        mode=SessionMode.HOME,
        status=SessionStatus.COMPLETED,
        actual_start_at=started,
        actual_end_at=ended,
        slot_id=slot_id,
    )
    db.add(session)
    db.flush()
    return session


def test_void_completed_with_slot_reverts_to_scheduled():
    db = SessionLocal()
    try:
        therapist, case_id = _therapist_and_case(db)
        today = today_ist()
        slot = TherapistSlot(
            therapist_user_id=therapist.id,
            slot_date=today,
            start_time=time(7, 30),
            end_time=time(8, 30),
            status=SlotStatus.BOOKED,
            case_id=case_id,
        )
        db.add(slot)
        db.flush()
        session = _completed_session(
            db, therapist_id=therapist.id, case_id=case_id, slot_id=slot.id
        )
        voided = session_service.void_session_before_log(db, session, therapist.id)
        assert voided.status == SessionStatus.SCHEDULED
        assert voided.actual_start_at is None
        assert voided.actual_end_at is None
        assert voided.cancellation_reason is None
    finally:
        db.close()


def test_void_completed_without_slot_marks_cancelled():
    db = SessionLocal()
    try:
        therapist, case_id = _therapist_and_case(db)
        session = _completed_session(db, therapist_id=therapist.id, case_id=case_id, slot_id=None)
        voided = session_service.void_session_before_log(db, session, therapist.id)
        assert voided.status == SessionStatus.CANCELLED
        assert voided.cancellation_reason == "void_before_log"
    finally:
        db.close()


def test_void_rejects_after_window(monkeypatch):
    db = SessionLocal()
    try:
        monkeypatch.setattr(settings, "session_void_window_hours", 24)
        therapist, case_id = _therapist_and_case(db)
        session = _completed_session(db, therapist_id=therapist.id, case_id=case_id, started_hours_ago=30)
        with pytest.raises(ValueError, match="Void window expired"):
            session_service.void_session_before_log(db, session, therapist.id)
    finally:
        db.close()


def test_void_rejects_in_progress():
    db = SessionLocal()
    try:
        therapist, case_id = _therapist_and_case(db)
        session = TherapySession(
            case_id=case_id,
            therapist_user_id=therapist.id,
            scheduled_date=today_ist(),
            mode=SessionMode.HOME,
            status=SessionStatus.IN_PROGRESS,
            actual_start_at=datetime.now(timezone.utc),
        )
        db.add(session)
        db.flush()
        with pytest.raises(ValueError, match="Only completed"):
            session_service.void_session_before_log(db, session, therapist.id)
    finally:
        db.close()


def test_cancel_in_progress_sets_audit_reason():
    db = SessionLocal()
    try:
        therapist, case_id = _therapist_and_case(db)
        session = TherapySession(
            case_id=case_id,
            therapist_user_id=therapist.id,
            scheduled_date=today_ist(),
            mode=SessionMode.HOME,
            status=SessionStatus.IN_PROGRESS,
            actual_start_at=datetime.now(timezone.utc),
        )
        db.add(session)
        db.flush()
        cancelled = session_service.cancel_session(db, session, therapist.id)
        assert cancelled.status == SessionStatus.SCHEDULED
        assert cancelled.cancellation_reason == "cancel_in_progress"
    finally:
        db.close()


def test_void_before_log_api_writes_audit_trail():
    from app.tests.test_session_day_end_autoclose import _therapist_headers, client

    headers = _therapist_headers()
    db = SessionLocal()
    try:
        therapist, case_id = _therapist_and_case(db)
        session = _completed_session(db, therapist_id=therapist.id, case_id=case_id, slot_id=None)
        db.commit()
        sid = session.id
    finally:
        db.close()

    res = client.post(f"/api/v1/sessions/{sid}/void-before-log", headers=headers, json={})
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "CANCELLED"

    db = SessionLocal()
    try:
        events = db.scalars(
            select(AuditEvent)
            .where(
                AuditEvent.entity_type == "session",
                AuditEvent.entity_id == str(sid),
                AuditEvent.action == "void_before_log",
            )
            .order_by(AuditEvent.id.desc())
        ).all()
        assert events, "expected void_before_log audit event"
        latest = events[0]
        assert latest.actor_user_id is not None
        assert latest.case_id == case_id
        assert '"scheduled_date"' in (latest.old_value or "")
        assert '"COMPLETED"' in (latest.old_value or "")
        assert '"CANCELLED"' in (latest.new_value or "")
    finally:
        db.close()
