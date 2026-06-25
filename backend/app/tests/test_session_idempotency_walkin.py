from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.api.v1.sessions import create_session
from app.core.database import SessionLocal
from app.models.case import Case
from app.models.daily_log import DailyLog
from app.models.session import Session as TherapySession
from app.models.session import SessionMode, SessionStatus
from app.models.user import User
from app.schemas.session import SessionCreate
from app.services import session_service
from app.core.timezone import today_ist


def test_end_session_idempotency():
    db = SessionLocal()
    isolated_day = date(2020, 3, 5)
    session_id = None
    try:
        therapist = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
        case = db.scalars(select(Case)).first()
        assert therapist and case

        start_at = datetime.combine(isolated_day, time(10, 0), tzinfo=timezone.utc)
        end_at = start_at + timedelta(minutes=30)
        session = TherapySession(
            case_id=case.id,
            therapist_user_id=therapist.id,
            scheduled_date=isolated_day,
            status=SessionStatus.IN_PROGRESS,
            actual_start_at=start_at,
            mode=SessionMode.HOME,
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        session_id = session.id

        ended = session_service.end_session(db, session, end_at=end_at)
        assert ended.status == SessionStatus.COMPLETED
        assert ended.actual_end_at is not None

        original_end_time = ended.actual_end_at

        ended_again = session_service.end_session(db, ended)
        assert ended_again.status == SessionStatus.COMPLETED
        assert ended_again.actual_end_at == original_end_time
    finally:
        if session_id is not None:
            session = db.get(TherapySession, session_id)
            if session:
                log = db.scalars(select(DailyLog).where(DailyLog.session_id == session_id)).first()
                if log:
                    db.delete(log)
                db.delete(session)
                db.commit()
        db.close()


def test_create_session_unresolved_same_day_duplicate():
    db = SessionLocal()
    try:
        therapist = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
        case = db.scalars(select(Case)).first()
        assert therapist and case

        today = today_ist()

        existing = db.scalars(
            select(TherapySession).where(
                TherapySession.case_id == case.id,
                TherapySession.therapist_user_id == therapist.id,
                TherapySession.scheduled_date == today,
            )
        ).all()
        for s in existing:
            log = db.scalars(select(DailyLog).where(DailyLog.session_id == s.id)).first()
            if log:
                db.delete(log)
            db.delete(s)
        db.commit()

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

        with pytest.raises(HTTPException) as exc_info:
            create_session(
                payload=payload,
                request=mock_request,
                user=therapist,
                db=db,
            )
        assert exc_info.value.status_code == 409
        detail = exc_info.value.detail
        assert detail["code"] == "EXISTING_SESSION_FOR_DATE"
        assert detail["session_id"] == first_created.id
        assert detail["status"] == SessionStatus.SCHEDULED.value
    finally:
        db.rollback()
        db.close()
