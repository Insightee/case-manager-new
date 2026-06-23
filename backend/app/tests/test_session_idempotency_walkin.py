from __future__ import annotations

from datetime import date, datetime, time, timezone
import pytest
from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.case import Case
from app.models.session import Session as TherapySession
from app.models.session import SessionStatus, SessionMode
from app.models.user import User
from app.services import session_service
from app.core.timezone import today_ist
from app.schemas.session import SessionCreate
from app.api.v1.sessions import create_session
from fastapi import HTTPException
from unittest.mock import MagicMock

def test_end_session_idempotency():
    db = SessionLocal()
    try:
        therapist = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
        case = db.scalars(select(Case)).first()
        assert therapist and case

        session = TherapySession(
            case_id=case.id,
            therapist_user_id=therapist.id,
            scheduled_date=date.today(),
            status=SessionStatus.IN_PROGRESS,
            actual_start_at=datetime.now(timezone.utc),
            mode=SessionMode.HOME,
        )
        db.add(session)
        db.commit()
        db.refresh(session)

        # First end session call should end it normally
        ended = session_service.end_session(db, session)
        assert ended.status == SessionStatus.COMPLETED
        assert ended.actual_end_at is not None

        original_end_time = ended.actual_end_at

        # Second end session call should return the completed session idempotently
        ended_again = session_service.end_session(db, ended)
        assert ended_again.status == SessionStatus.COMPLETED
        assert ended_again.actual_end_at == original_end_time
    finally:
        db.rollback()
        db.close()


def test_create_session_unresolved_same_day_duplicate():
    db = SessionLocal()
    try:
        therapist = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
        case = db.scalars(select(Case)).first()
        assert therapist and case
        
        today = today_ist()

        # Let's clean up existing same day sessions if any
        existing = db.scalars(
            select(TherapySession).where(
                TherapySession.case_id == case.id,
                TherapySession.therapist_user_id == therapist.id,
                TherapySession.scheduled_date == today,
            )
        ).all()
        for s in existing:
            db.delete(s)
        db.commit()

        # 1. Create a scheduled session for today
        payload = SessionCreate(
            case_id=case.id,
            therapist_user_id=therapist.id,
            scheduled_date=today,
            start_time="10:00",
            end_time="11:00",
            mode=SessionMode.HOME,
            status=SessionStatus.SCHEDULED,
        )

        mock_request = MagicMock()
        mock_request.client.host = "127.0.0.1"
        mock_request.headers = {}

        first_created = create_session(
            payload=payload,
            request=mock_request,
            user=therapist,
            db=db,
        )
        assert first_created.id is not None
        assert first_created.status == SessionStatus.SCHEDULED

        # 2. Attempt to create another one for same day. Should return the existing one.
        second_created = create_session(
            payload=payload,
            request=mock_request,
            user=therapist,
            db=db,
        )
        assert second_created.id == first_created.id
    finally:
        db.rollback()
        db.close()
