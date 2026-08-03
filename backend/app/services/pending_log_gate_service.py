"""Block new session work until the therapist's latest visit has a submitted log."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.session_start import PendingLogRequiredError
from app.models.case import Case
from app.models.daily_log import DailyLog
from app.models.session import Session as TherapySession
from app.models.session import SessionStatus

PENDING_LOG_MESSAGE = (
    "Your most recent visit still needs a session log before you can start another. "
    "Complete that log or remove the draft visit to continue."
)


def get_blocking_session(db: Session, therapist_user_id: int) -> TherapySession | None:
    """Most recent COMPLETED visit with no daily log — only this one blocks new sessions."""
    return db.scalars(
        select(TherapySession)
        .outerjoin(DailyLog, DailyLog.session_id == TherapySession.id)
        .where(
            TherapySession.therapist_user_id == therapist_user_id,
            TherapySession.status == SessionStatus.COMPLETED,
            DailyLog.id.is_(None),
        )
        .options(
            selectinload(TherapySession.daily_log),
            selectinload(TherapySession.case).selectinload(Case.child),
        )
        .order_by(TherapySession.scheduled_date.desc(), TherapySession.id.desc())
        .limit(1)
    ).first()


def is_blocking_session(db: Session, therapist_user_id: int, session_id: int) -> bool:
    blocking = get_blocking_session(db, therapist_user_id)
    return blocking is not None and blocking.id == session_id


def assert_may_start_new_session(
    db: Session,
    therapist_user_id: int,
    *,
    excluding_session_id: int | None = None,
) -> None:
    blocking = get_blocking_session(db, therapist_user_id)
    if not blocking:
        return
    if excluding_session_id is not None and blocking.id == excluding_session_id:
        return
    raise PendingLogRequiredError(
        blocking_session_id=blocking.id,
        message=PENDING_LOG_MESSAGE,
    )


def discard_blocking_draft_log(
    db: Session,
    session: TherapySession,
    therapist_user_id: int,
) -> TherapySession:
    from app.services import session_service

    if session.therapist_user_id != therapist_user_id:
        raise ValueError("Not your session")
    if not is_blocking_session(db, therapist_user_id, session.id):
        raise ValueError("Only your latest unfinished visit can be removed this way")
    return session_service.void_session_before_log(
        db,
        session,
        therapist_user_id,
        skip_void_window=True,
    )
