from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.core.timezone import IST, today_ist, wall_clock_time_ist, ensure_utc_aware
from app.core.session_rules import (
    MIN_SESSION_DURATION_ERROR,
    compute_auto_end_cap,
    duration_minutes_between,
    product_module_for_case,
    resolve_clinical_service_category,
    scheduled_duration_minutes,
    validate_session_duration_minutes,
)
from app.core.session_start import RecommendedAction, SessionStartConflict
from app.models.daily_log import LogApprovalStatus
from app.models.session import Session as TherapySession
from app.models.session import SessionMode, SessionStatus
from app.services import session_start_service as start_svc


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def session_ist_calendar_day(session: TherapySession) -> date:
    """IST calendar day for an open or scheduled session."""
    if session.actual_start_at:
        return _aware(session.actual_start_at).astimezone(IST).date()
    return session.scheduled_date


def get_in_progress_sessions(db: Session, therapist_user_id: int) -> list[TherapySession]:
    return list(
        db.scalars(
            select(TherapySession)
            .where(
                TherapySession.therapist_user_id == therapist_user_id,
                TherapySession.status == SessionStatus.IN_PROGRESS,
            )
            .options(selectinload(TherapySession.case), selectinload(TherapySession.daily_log))
            .order_by(TherapySession.actual_start_at.desc())
        ).all()
    )


def partition_sessions_by_ist_day(
    sessions: list[TherapySession],
    *,
    today: date | None = None,
) -> tuple[list[TherapySession], list[TherapySession]]:
    today = today or today_ist()
    same_day: list[TherapySession] = []
    stale: list[TherapySession] = []
    for session in sessions:
        if session_ist_calendar_day(session) == today:
            same_day.append(session)
        else:
            stale.append(session)
    return same_day, stale


def get_active_session_for_today(db: Session, therapist_user_id: int) -> TherapySession | None:
    """Same IST-day IN_PROGRESS only — blocks starting another live session."""
    same_day, _ = partition_sessions_by_ist_day(get_in_progress_sessions(db, therapist_user_id))
    if not same_day:
        return None
    session = same_day[0]
    session = auto_end_if_stale(db, session)
    if session.status == SessionStatus.IN_PROGRESS:
        db.flush()
        return session
    db.commit()
    return None


def get_stale_previous_sessions(db: Session, therapist_user_id: int) -> list[TherapySession]:
    """Prior IST-day IN_PROGRESS — informational; does not block today's work."""
    _, stale = partition_sessions_by_ist_day(get_in_progress_sessions(db, therapist_user_id))
    return stale


def auto_end_if_stale(db: Session, session: TherapySession) -> TherapySession:
    if session.status != SessionStatus.IN_PROGRESS or not session.actual_start_at:
        return session
    started = _aware(session.actual_start_at)
    module = product_module_for_case(session.case)
    category = resolve_clinical_service_category(session.case, db=db)
    hard_cap, reason, sched_mins, overage = compute_auto_end_cap(
        started_at=started,
        scheduled_date=session.scheduled_date,
        start_time=session.start_time,
        end_time=session.end_time,
        product_module=module,
        service_category=category,
    )
    if _now() >= hard_cap:
        session.scheduled_duration_mins = sched_mins
        session.overage_mins = overage
        session.time_confirmation_required = True
        return end_session(
            db,
            session,
            auto_ended=True,
            end_at=hard_cap,
            auto_end_reason=reason,
        )
    return session


def get_active_session(db: Session, therapist_user_id: int) -> TherapySession | None:
    """Same-day live session only (backward-compatible alias)."""
    return get_active_session_for_today(db, therapist_user_id)


def start_session(
    db: Session,
    session: TherapySession,
    therapist_user_id: int,
    *,
    lat: float | None = None,
    lng: float | None = None,
    idempotency_key: str | None = None,
    allow_duplicate: bool = False,
) -> TherapySession:
    if session.therapist_user_id != therapist_user_id:
        raise ValueError("Not your session")

    cached = start_svc.get_idempotent_session(
        db, idempotency_key=idempotency_key, therapist_user_id=therapist_user_id
    )
    if cached and cached.status == SessionStatus.IN_PROGRESS:
        return cached

    if session.status == SessionStatus.IN_PROGRESS:
        session.resumed_count = (session.resumed_count or 0) + 1
        db.flush()
        start_svc.store_idempotency(
            db,
            idempotency_key=idempotency_key or start_svc.default_idempotency_key(therapist_user_id, session),
            therapist_user_id=therapist_user_id,
            session_id=session.id,
        )
        return session

    if session.status != SessionStatus.SCHEDULED:
        if session.status == SessionStatus.COMPLETED:
            log = session.daily_log
            if log is None:
                action = RecommendedAction.COMPLETE_LOG
            elif log.approval_status == LogApprovalStatus.REJECTED:
                action = RecommendedAction.EDIT_LOG
            elif log.approval_status == LogApprovalStatus.PENDING:
                action = RecommendedAction.EDIT_LOG
            else:
                action = RecommendedAction.VIEW_EXISTING
            raise SessionStartConflict(
                existing_session_id=session.id,
                current_status=session.status.value,
                recommended_action=action,
                message="A session already exists for this visit.",
            )
        raise ValueError("Session is not scheduled")

    from app.services.assignment_acceptance_service import assert_therapist_may_start_session

    assert_therapist_may_start_session(db, session.case_id)
    start_svc.resolve_start_conflict(db, session, therapist_user_id, allow_duplicate=allow_duplicate)

    today = today_ist()
    for active in get_in_progress_sessions(db, therapist_user_id):
        if active.id == session.id:
            continue
        if session_ist_calendar_day(active) != today:
            continue
        active = auto_end_if_stale(db, active)
        if active.status == SessionStatus.IN_PROGRESS:
            raise SessionStartConflict(
                existing_session_id=active.id,
                current_status=active.status.value,
                recommended_action=RecommendedAction.CONTINUE_SESSION,
                message="You already have an active session. Continue it before starting another.",
            )

    now = _now()
    if allow_duplicate:
        session.is_additional_visit = True
    session.status = SessionStatus.IN_PROGRESS
    session.actual_start_at = now
    sched_mins = scheduled_duration_minutes(
        start_time=session.start_time,
        end_time=session.end_time,
        slot_duration_minutes=session.slot_duration_minutes,
    )
    session.scheduled_duration_mins = sched_mins
    if lat is not None:
        session.checkin_lat = lat
    if lng is not None:
        session.checkin_lng = lng
    db.flush()
    if session.case_id:
        from app.services.case_status_request_service import assert_case_allows_new_session

        assert_case_allows_new_session(db, session.case_id)

    key = idempotency_key or start_svc.default_idempotency_key(therapist_user_id, session)
    start_svc.store_idempotency(
        db,
        idempotency_key=key,
        therapist_user_id=therapist_user_id,
        session_id=session.id,
    )
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
    if session.status == SessionStatus.COMPLETED:
        return session
    if session.status != SessionStatus.IN_PROGRESS:
        raise ValueError("Session is not in progress")
    end_time = _aware(end_at) if end_at else _now()
    if session.actual_start_at:
        mins = duration_minutes_between(session.actual_start_at, end_time)
        if not auto_ended:
            validate_session_duration_minutes(mins)
    session.status = SessionStatus.COMPLETED
    session.actual_end_at = end_time
    session.auto_ended = auto_ended
    session.auto_end_reason = auto_end_reason if auto_ended else None
    if lat is not None:
        session.checkout_lat = lat
    if lng is not None:
        session.checkout_lng = lng
    start_svc.clear_idempotency_for_session(db, session.id)
    db.flush()
    return session


def session_audit_snapshot(session: TherapySession) -> dict:
    """Structured session fields for audit events (who voided/cancelled which visit on which day)."""
    status = session.status.value if hasattr(session.status, "value") else str(session.status)
    return {
        "session_id": session.id,
        "case_id": session.case_id,
        "therapist_user_id": session.therapist_user_id,
        "scheduled_date": session.scheduled_date.isoformat() if session.scheduled_date else None,
        "status": status,
        "slot_id": session.slot_id,
        "actual_start_at": session.actual_start_at.isoformat() if session.actual_start_at else None,
        "actual_end_at": session.actual_end_at.isoformat() if session.actual_end_at else None,
        "cancellation_reason": session.cancellation_reason,
        "auto_ended": bool(session.auto_ended),
        "is_additional_visit": bool(session.is_additional_visit),
    }


def _void_window_anchor(session: TherapySession) -> datetime:
    if session.actual_start_at:
        return ensure_utc_aware(session.actual_start_at)
    day_start = datetime.combine(session.scheduled_date, time.min, tzinfo=IST)
    return day_start.astimezone(timezone.utc)


def void_session_before_log(
    db: Session,
    session: TherapySession,
    therapist_user_id: int,
) -> TherapySession:
    """Void a completed visit that has no log — revert scheduled slots or cancel unbooked/manual rows."""
    if session.therapist_user_id != therapist_user_id:
        raise ValueError("Not your session")
    if session.status != SessionStatus.COMPLETED:
        raise ValueError("Only completed sessions without a log can be voided")
    if session.daily_log is not None:
        raise ValueError("Cannot void a session that already has a log")

    from app.models.ledger_billing import BillingLedger
    from app.services import session_absence_service as absence_svc

    has_ledger = db.scalars(select(BillingLedger).where(BillingLedger.session_id == session.id)).first()
    if has_ledger:
        raise ValueError("Billing records exist for this session — contact your case manager")

    if absence_svc.has_blocking_absence_for_session(db, session.id):
        raise ValueError("An absence request is linked to this session — contact your case manager")

    anchor = _void_window_anchor(session)
    window = timedelta(hours=settings.session_void_window_hours)
    if datetime.now(timezone.utc) > anchor + window:
        hours = settings.session_void_window_hours
        raise ValueError(
            f"Void window expired — sessions can only be cancelled within {hours} hours of starting"
        )

    _clear_visit_clock_fields(session)
    if session.slot_id is not None:
        session.status = SessionStatus.SCHEDULED
        session.cancellation_reason = None
    else:
        session.status = SessionStatus.CANCELLED
        session.cancellation_reason = "void_before_log"
    start_svc.clear_idempotency_for_session(db, session.id)
    db.flush()
    return session


def _clear_visit_clock_fields(session: TherapySession) -> None:
    session.actual_start_at = None
    session.actual_end_at = None
    session.auto_ended = False
    session.auto_end_reason = None
    session.scheduled_duration_mins = None
    session.overage_mins = None
    session.time_confirmation_required = False
    session.checkin_lat = None
    session.checkin_lng = None
    session.checkout_lat = None
    session.checkout_lng = None
    session.edited_start_at = None
    session.edited_end_at = None
    session.actual_times_edited = False
    session.actual_times_edited_at = None
    session.actual_times_edited_by = None
    session.actual_times_edit_reason = None


def cancel_session(
    db: Session,
    session: TherapySession,
    therapist_user_id: int,
) -> TherapySession:
    """Revert an accidental start — session returns to scheduled with no visit recorded."""
    if session.therapist_user_id != therapist_user_id:
        raise ValueError("Not your session")
    if session.status != SessionStatus.IN_PROGRESS:
        raise ValueError("Session is not in progress")
    if session.daily_log is not None:
        raise ValueError("Cannot cancel a session that already has a log")
    _clear_visit_clock_fields(session)
    session.status = SessionStatus.SCHEDULED
    session.cancellation_reason = "cancel_in_progress"
    start_svc.clear_idempotency_for_session(db, session.id)
    db.flush()
    return session


def update_actual_times(
    db: Session,
    session: TherapySession,
    therapist_user_id: int,
    *,
    actual_start_at: datetime,
    actual_end_at: datetime,
    edit_reason: str,
) -> TherapySession:
    if session.therapist_user_id != therapist_user_id:
        raise ValueError("Not your session")
    if session.status != SessionStatus.COMPLETED:
        raise ValueError("Only completed sessions can have times edited")
    log = session.daily_log
    rejected_resubmit = log and log.approval_status == LogApprovalStatus.REJECTED
    if session.actual_end_at and not rejected_resubmit:
        from app.services.log_service import LOG_EDIT_WINDOW

        ended = _aware(session.actual_end_at)
        if datetime.now(timezone.utc) > ended + LOG_EDIT_WINDOW:
            raise ValueError("Actual times can only be edited within 24 hours of session end")
    reason = (edit_reason or "").strip()
    if len(reason) < 5:
        raise ValueError("Edit reason is required (at least 5 characters)")
    if actual_end_at <= actual_start_at:
        raise ValueError("End time must be after start time")
    validate_session_duration_minutes(duration_minutes_between(actual_start_at, actual_end_at))

    session.edited_start_at = _aware(actual_start_at)
    session.edited_end_at = _aware(actual_end_at)
    session.actual_times_edited = True
    session.actual_times_edited_at = _now()
    session.actual_times_edited_by = therapist_user_id
    session.actual_times_edit_reason = reason
    session.time_confirmation_required = False
    db.flush()

    if log and log.approval_status != LogApprovalStatus.REJECTED:
        log.approval_status = LogApprovalStatus.PENDING.value
        db.flush()
    return session


def list_upcoming_sessions(
    db: Session,
    therapist_user_id: int,
    *,
    days: int = 7,
) -> list[TherapySession]:
    today = today_ist()
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
        start_time=wall_clock_time_ist(actual_start_at),
        end_time=wall_clock_time_ist(actual_end_at),
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


__all__ = [
    "MIN_SESSION_DURATION_ERROR",
    "create_manual_session",
    "session_audit_snapshot",
    "void_session_before_log",
    "validate_manual_duration",
]
