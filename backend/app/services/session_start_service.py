from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.session_start import RecommendedAction, SessionStartConflict
from app.core.timezone import today_ist
from app.models.daily_log import LogApprovalStatus
from app.models.session import Session as TherapySession
from app.models.session import SessionStatus
from app.models.session_start_idempotency import SessionStartIdempotency


def _matching_sessions_stmt(session: TherapySession):
    """Sessions representing the same canonical visit (excluding cancelled/rescheduled)."""
    active_statuses = (
        SessionStatus.SCHEDULED,
        SessionStatus.IN_PROGRESS,
        SessionStatus.COMPLETED,
    )
    if session.slot_id:
        return select(TherapySession).where(
            TherapySession.slot_id == session.slot_id,
            TherapySession.case_id == session.case_id,
            TherapySession.therapist_user_id == session.therapist_user_id,
            TherapySession.scheduled_date == session.scheduled_date,
            TherapySession.status.in_(active_statuses),
        )
    return select(TherapySession).where(
        TherapySession.case_id == session.case_id,
        TherapySession.therapist_user_id == session.therapist_user_id,
        TherapySession.scheduled_date == session.scheduled_date,
        TherapySession.slot_id.is_(None),
        TherapySession.status.in_(active_statuses),
    )


def _recommended_for_completed(session: TherapySession) -> RecommendedAction:
    log = session.daily_log
    if log is None:
        return RecommendedAction.COMPLETE_LOG
    status = log.approval_status
    if status == LogApprovalStatus.REJECTED:
        return RecommendedAction.EDIT_LOG
    if status == LogApprovalStatus.PENDING:
        return RecommendedAction.EDIT_LOG
    return RecommendedAction.VIEW_EXISTING


def resolve_start_conflict(
    db: Session,
    session: TherapySession,
    therapist_user_id: int,
    *,
    allow_duplicate: bool = False,
) -> None:
    """Raise SessionStartConflict when another matching visit blocks a fresh start."""
    if session.therapist_user_id != therapist_user_id:
        raise ValueError("Not your session")

    today = today_ist()
    if session.scheduled_date > today:
        raise ValueError(
            "Sessions can only be started on the scheduled visit date. "
            "Use Forgot to log after the visit if you missed clocking in."
        )
    if session.scheduled_date < today:
        raise ValueError(
            "This visit was scheduled for another day. Use Forgot to log to record it."
        )

    matches = db.scalars(
        _matching_sessions_stmt(session).options(selectinload(TherapySession.daily_log))
    ).all()

    for match in matches:
        if match.id == session.id:
            continue
        if match.status == SessionStatus.IN_PROGRESS:
            raise SessionStartConflict(
                existing_session_id=match.id,
                current_status=match.status.value,
                recommended_action=RecommendedAction.CONTINUE_SESSION,
                message="A session already exists for this visit. Continue the existing session rather than starting another one.",
            )
        if match.status == SessionStatus.COMPLETED:
            if allow_duplicate:
                continue
            same_day_other = (
                match.id != session.id
                and match.scheduled_date == session.scheduled_date
                and match.case_id == session.case_id
            )
            action = (
                RecommendedAction.DUPLICATE_SAME_DAY
                if same_day_other
                else _recommended_for_completed(match)
            )
            raise SessionStartConflict(
                existing_session_id=match.id,
                current_status=match.status.value,
                recommended_action=action,
                message=(
                    "You already completed a session for this client today. "
                    "Edit the existing session or start another visit explicitly."
                    if same_day_other
                    else "A session already exists for this visit."
                ),
            )

    if allow_duplicate:
        return

    other_today = db.scalars(
        select(TherapySession)
        .where(
            TherapySession.case_id == session.case_id,
            TherapySession.therapist_user_id == therapist_user_id,
            TherapySession.scheduled_date == session.scheduled_date,
            TherapySession.id != session.id,
            TherapySession.status.in_((SessionStatus.IN_PROGRESS, SessionStatus.COMPLETED)),
        )
        .options(selectinload(TherapySession.daily_log))
    ).all()
    for other in other_today:
        if other.status == SessionStatus.IN_PROGRESS:
            raise SessionStartConflict(
                existing_session_id=other.id,
                current_status=other.status.value,
                recommended_action=RecommendedAction.CONTINUE_SESSION,
                message="A session is already in progress for this client today.",
            )
        raise SessionStartConflict(
            existing_session_id=other.id,
            current_status=other.status.value,
            recommended_action=RecommendedAction.DUPLICATE_SAME_DAY,
            message=(
                "You already completed a session for this client today. "
                "Edit the existing session or start another visit explicitly."
            ),
        )


def get_idempotent_session(
    db: Session,
    *,
    idempotency_key: str | None,
    therapist_user_id: int,
) -> TherapySession | None:
    if not idempotency_key or not idempotency_key.strip():
        return None
    key = idempotency_key.strip()
    row = db.scalars(
        select(SessionStartIdempotency).where(SessionStartIdempotency.idempotency_key == key)
    ).first()
    if not row or row.therapist_user_id != therapist_user_id:
        return None
    return db.scalars(
        select(TherapySession)
        .where(TherapySession.id == row.session_id)
        .options(selectinload(TherapySession.case), selectinload(TherapySession.daily_log))
    ).first()


def clear_idempotency_for_session(db: Session, session_id: int) -> None:
    """Drop cached start keys when a visit ends or is voided so the slot can be started again."""
    from sqlalchemy import delete

    db.execute(delete(SessionStartIdempotency).where(SessionStartIdempotency.session_id == session_id))
    db.flush()


def store_idempotency(
    db: Session,
    *,
    idempotency_key: str | None,
    therapist_user_id: int,
    session_id: int,
) -> None:
    if not idempotency_key or not idempotency_key.strip():
        return
    key = idempotency_key.strip()
    existing = db.scalars(
        select(SessionStartIdempotency).where(SessionStartIdempotency.idempotency_key == key)
    ).first()
    if existing:
        return
    db.add(
        SessionStartIdempotency(
            idempotency_key=key,
            session_id=session_id,
            therapist_user_id=therapist_user_id,
        )
    )
    db.flush()


def default_idempotency_key(therapist_user_id: int, session: TherapySession) -> str:
    slot_part = session.slot_id or session.id
    return f"{therapist_user_id}-{slot_part}-{session.scheduled_date.isoformat()}"
