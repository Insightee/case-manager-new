from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.session import Session as TherapySession
from app.models.session import SessionMode, SessionStatus

SESSION_MAX_DURATION = timedelta(hours=2)
# Fallback auto-end threshold when no slot duration is known
SESSION_FALLBACK_MAX_HOURS = 4


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _auto_end_threshold(session: TherapySession) -> timedelta:
    """Return the stale-session threshold. Uses slot_duration_minutes * 1.5 if known."""
    if session.slot_duration_minutes and session.slot_duration_minutes > 0:
        return timedelta(seconds=session.slot_duration_minutes * 60 * 1.5)
    return timedelta(hours=SESSION_FALLBACK_MAX_HOURS)


def auto_end_if_stale(db: Session, session: TherapySession) -> TherapySession:
    if session.status != SessionStatus.IN_PROGRESS or not session.actual_start_at:
        return session
    started = session.actual_start_at
    if started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)
    if _now() - started > _auto_end_threshold(session):
        return end_session(db, session, auto_ended=True)
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
    return session


def end_session(
    db: Session,
    session: TherapySession,
    *,
    auto_ended: bool = False,
    lat: float | None = None,
    lng: float | None = None,
) -> TherapySession:
    if session.status != SessionStatus.IN_PROGRESS:
        raise ValueError("Session is not in progress")
    now = _now()
    session.status = SessionStatus.COMPLETED
    session.actual_end_at = now
    session.end_time = now.time().replace(second=0, microsecond=0)
    if session.actual_start_at and not session.start_time:
        session.start_time = session.actual_start_at.time().replace(second=0, microsecond=0)
    session.auto_ended = auto_ended
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
    today = date.today()
    if scheduled_date > today:
        raise ValueError("Cannot create manual sessions for future dates")
    if actual_end_at <= actual_start_at:
        raise ValueError("End time must be after start time")
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
