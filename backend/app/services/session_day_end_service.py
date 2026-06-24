"""Auto-close open IN_PROGRESS sessions at 10 PM IST (day-end job + workspace safety hook)."""

from __future__ import annotations

import logging
from datetime import datetime, time, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.session_rules import (
    compute_auto_end_cap,
    product_module_for_case,
    resolve_clinical_service_category,
)
from app.core.timezone import IST, ensure_utc_aware, now_ist
from app.models.session import Session as TherapySession
from app.models.session import SessionStatus
from app.services.session_service import end_session, session_ist_calendar_day

logger = logging.getLogger("insightcase.session_day_end")

DAY_END_IST = time(22, 0)
REASON_TODAY = "day_end_10pm_ist"
REASON_HISTORICAL = "historical_cleanup_at_day_end"


def _day_end_ist_datetime(day) -> datetime:
    return datetime.combine(day, DAY_END_IST, tzinfo=IST)


def _historical_end_at(session: TherapySession, now_ist_dt: datetime, db: Session) -> datetime:
    """Cap historical open sessions — never extend work into today."""
    session_day = session_ist_calendar_day(session)
    day_cap = _day_end_ist_datetime(session_day).astimezone(timezone.utc)
    started = ensure_utc_aware(session.actual_start_at)
    assert started is not None
    module = product_module_for_case(session.case)
    category = resolve_clinical_service_category(session.case, db=db)
    hard_cap, _, _, _ = compute_auto_end_cap(
        started_at=started,
        scheduled_date=session.scheduled_date,
        start_time=session.start_time,
        end_time=session.end_time,
        product_module=module,
        service_category=category,
    )
    end_utc = min(day_cap, hard_cap)
    today_start = _day_end_ist_datetime(now_ist_dt.date()).replace(hour=0, minute=0, second=0, microsecond=0)
    today_start_utc = today_start.astimezone(timezone.utc)
    if end_utc >= today_start_utc:
        end_utc = day_cap
    return end_utc


def auto_close_open_sessions_at_day_end(db: Session, now_ist_dt: datetime | None = None) -> list[int]:
    """
    Close all IN_PROGRESS sessions at day end. No DailyLog creation.
    Intended to run at or after 22:00 IST (cron + opportunistic workspace hook).
    """
    now_ist_dt = now_ist_dt or now_ist()
    if now_ist_dt.tzinfo is None:
        now_ist_dt = now_ist_dt.replace(tzinfo=IST)
    else:
        now_ist_dt = now_ist_dt.astimezone(IST)

    today = now_ist_dt.date()
    rows = list(
        db.scalars(
            select(TherapySession)
            .where(
                TherapySession.status == SessionStatus.IN_PROGRESS,
                TherapySession.actual_start_at.is_not(None),
            )
            .options(selectinload(TherapySession.case))
            .order_by(TherapySession.actual_start_at.asc())
        ).all()
    )
    closed_ids: list[int] = []
    for session in rows:
        old_status = session.status.value
        session_day = session_ist_calendar_day(session)
        if session_day == today:
            end_at = _day_end_ist_datetime(today).astimezone(timezone.utc)
            reason = REASON_TODAY
            trigger = "auto_close_10pm"
        else:
            end_at = _historical_end_at(session, now_ist_dt, db)
            reason = REASON_HISTORICAL
            trigger = "historical_cleanup_at_day_end"

        end_session(
            db,
            session,
            auto_ended=True,
            end_at=end_at,
            auto_end_reason=reason,
        )
        session.time_confirmation_required = True
        closed_ids.append(session.id)
        logger.info(
            "session_day_end_close session_id=%s therapist_user_id=%s case_id=%s "
            "old_status=%s new_status=%s trigger=%s auto_end_reason=%s ended_at=%s",
            session.id,
            session.therapist_user_id,
            session.case_id,
            old_status,
            session.status.value,
            trigger,
            reason,
            session.actual_end_at,
        )
    if closed_ids:
        db.flush()
    return closed_ids


def close_previous_day_open_sessions(db: Session, now_ist_dt: datetime | None = None) -> list[int]:
    """
    One-time / maintenance: close IN_PROGRESS sessions from prior IST calendar days only.
    Does not touch same-day live sessions.
    """
    now_ist_dt = now_ist_dt or now_ist()
    if now_ist_dt.tzinfo is None:
        now_ist_dt = now_ist_dt.replace(tzinfo=IST)
    else:
        now_ist_dt = now_ist_dt.astimezone(IST)

    today = now_ist_dt.date()
    rows = list(
        db.scalars(
            select(TherapySession)
            .where(
                TherapySession.status == SessionStatus.IN_PROGRESS,
                TherapySession.actual_start_at.is_not(None),
            )
            .options(selectinload(TherapySession.case))
            .order_by(TherapySession.actual_start_at.asc())
        ).all()
    )
    closed_ids: list[int] = []
    for session in rows:
        session_day = session_ist_calendar_day(session)
        if session_day >= today:
            continue
        old_status = session.status.value
        end_at = _historical_end_at(session, now_ist_dt, db)
        end_session(
            db,
            session,
            auto_ended=True,
            end_at=end_at,
            auto_end_reason=REASON_HISTORICAL,
        )
        session.time_confirmation_required = True
        closed_ids.append(session.id)
        logger.info(
            "previous_day_cleanup session_id=%s therapist_user_id=%s case_id=%s "
            "old_status=%s new_status=%s auto_end_reason=%s ended_at=%s",
            session.id,
            session.therapist_user_id,
            session.case_id,
            old_status,
            session.status.value,
            REASON_HISTORICAL,
            session.actual_end_at,
        )
    if closed_ids:
        db.flush()
    return closed_ids
