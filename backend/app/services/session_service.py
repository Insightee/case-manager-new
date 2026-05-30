from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.session_rules import (
    MIN_SESSION_DURATION_ERROR,
    auto_end_reason_for_module,
    auto_end_threshold_for_module,
    duration_minutes_between,
    product_module_for_case,
    validate_session_duration_minutes,
)
from app.models.session import Session as TherapySession
from app.models.session import SessionMode, SessionStatus


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _auto_end_threshold(session: TherapySession) -> timedelta:
    module = product_module_for_case(session.case)
    return auto_end_threshold_for_module(module, session.slot_duration_minutes)


def auto_end_if_stale(db: Session, session: TherapySession) -> TherapySession:
    if session.status != SessionStatus.IN_PROGRESS or not session.actual_start_at:
        return session
    started = _aware(session.actual_start_at)
    threshold = _auto_end_threshold(session)
    cap_at = started + threshold
    if _now() >= cap_at:
        module = product_module_for_case(session.case)
        reason = auto_end_reason_for_module(module)
        return end_session(
            db,
            session,
            auto_ended=True,
            end_at=cap_at,
            auto_end_reason=reason,
        )
    return session


def get_active_session(db: Session, therapist_user_id: int) -> TherapySession | None:
    session = db.scalars(
        select(TherapySession)
        .where(
            TherapySession.therapist_user_id == therapist_user_id,
            TherapySession.status == SessionStatus.IN_PROGRESS,
        )
        .options(selectinload(TherapySession.case), selectinload(TherapySession.daily_log))
        .order_by(TherapySession.actual_start_at.desc())
    ).first()
    if session:
        session = auto_end_if_stale(db, session)
        if session.status == SessionStatus.IN_PROGRESS:
            db.flush()
            return session
        db.commit()
    return None


def start_session(
    db: Session,
    session: TherapySession,
    therapist_user_id: int,
    *,
    lat: float | None = None,
    lng: float | None = None,
) -> TherapySession:
    if session.therapist_user_id != therapist_user_id:
        raise ValueError("Not your session")
    if session.status != SessionStatus.SCHEDULED:
        raise ValueError("Session is not scheduled")
    from app.services.assignment_acceptance_service import assert_therapist_may_start_session

    assert_therapist_may_start_session(db, session.case_id)
    active = db.scalars(
        select(TherapySession).where(
            TherapySession.therapist_user_id == therapist_user_id,
            TherapySession.status == SessionStatus.IN_PROGRESS,
        )
    ).first()
    if active and active.id != session.id:
        active = auto_end_if_stale(db, active)
        if active.status == SessionStatus.IN_PROGRESS:
            raise ValueError("Finish your current session before starting another")
    now = _now()
    session.status = SessionStatus.IN_PROGRESS
    session.actual_start_at = now
    if not session.start_time:
        session.start_time = now.time().replace(second=0, microsecond=0)
    if lat is not None:
        session.checkin_lat = lat
    if lng is not None:
        session.checkin_lng = lng
    db.flush()
    if session.case_id:
        from app.services.case_status_request_service import assert_case_allows_new_session

        assert_case_allows_new_session(db, session.case_id)
    return session


def end_session(
    db: Session,
    session: TherapySession,
    *,
    auto_ended: bool = False,
    end_at: datetime | None = None,
    auto_end_reason: str | None = None,
    lat: float | None = None,
    lng: float | None = None,
) -> TherapySession:
    if session.status != SessionStatus.IN_PROGRESS:
        raise ValueError("Session is not in progress")
    end_time = _aware(end_at) if end_at else _now()
    if session.actual_start_at:
        mins = duration_minutes_between(session.actual_start_at, end_time)
        if not auto_ended:
            validate_session_duration_minutes(mins)
    session.status = SessionStatus.COMPLETED
    session.actual_end_at = end_time
    session.end_time = end_time.time().replace(second=0, microsecond=0)
    if session.actual_start_at and not session.start_time:
        session.start_time = _aware(session.actual_start_at).time().replace(second=0, microsecond=0)
    session.auto_ended = auto_ended
    session.auto_end_reason = auto_end_reason if auto_ended else None
    if lat is not None:
        session.checkout_lat = lat
    if lng is not None:
        session.checkout_lng = lng
    db.flush()
    return session


def list_upcoming_sessions(
    db: Session,
    therapist_user_id: int,
    *,
    days: int = 7,
) -> list[TherapySession]:
    today = date.today()
    end = today + timedelta(days=days)
    sessions = db.scalars(
        select(TherapySession)
        .where(
            TherapySession.therapist_user_id == therapist_user_id,
            TherapySession.status == SessionStatus.SCHEDULED,
            TherapySession.scheduled_date >= today,
            TherapySession.scheduled_date <= end,
        )
        .options(selectinload(TherapySession.case), selectinload(TherapySession.daily_log))
        .order_by(TherapySession.scheduled_date, TherapySession.start_time)
    ).all()
    return list(sessions)


def create_manual_session(
    db: Session,
    *,
    case_id: int,
    therapist_user_id: int,
    scheduled_date: date,
    actual_start_at: datetime,
    actual_end_at: datetime,
    mode: SessionMode,
) -> TherapySession:
    from app.core.timezone import today_ist

    today = today_ist()
    if scheduled_date > today:
        raise ValueError("Cannot create manual sessions for future dates")
    if actual_end_at <= actual_start_at:
        raise ValueError("End time must be after start time")
    mins = duration_minutes_between(actual_start_at, actual_end_at)
    validate_session_duration_minutes(mins)
    session = TherapySession(
        case_id=case_id,
        therapist_user_id=therapist_user_id,
        scheduled_date=scheduled_date,
        start_time=actual_start_at.time().replace(second=0, microsecond=0),
        end_time=actual_end_at.time().replace(second=0, microsecond=0),
        mode=mode,
        status=SessionStatus.COMPLETED,
        actual_start_at=actual_start_at,
        actual_end_at=actual_end_at,
    )
    db.add(session)
    db.flush()
    return session


def validate_manual_duration(actual_start_at: datetime, actual_end_at: datetime) -> None:
    """Re-export for invoice late-session paths."""
    if actual_end_at <= actual_start_at:
        raise ValueError("End time must be after start time")
    validate_session_duration_minutes(duration_minutes_between(actual_start_at, actual_end_at))


__all__ = ["MIN_SESSION_DURATION_ERROR", "create_manual_session", "validate_manual_duration"]
