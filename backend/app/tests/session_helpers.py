"""Test helpers for therapist session start/end flows."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.assignment import CaseAssignment, CaseAssignmentStatus
from app.models.session import Session as TherapySession
from app.models.session import SessionMode, SessionStatus
from app.models.user import User
from app.services import session_service


def backdate_in_progress_session(session_id: int, minutes_ago: int = 6) -> None:
    """Set actual_start_at so manual end passes the 5-minute minimum rule."""
    db = SessionLocal()
    try:
        session = db.get(TherapySession, session_id)
        if session is None:
            raise ValueError(f"Session {session_id} not found")
        session.actual_start_at = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
        db.commit()
    finally:
        db.close()


def end_active_sessions_for_therapist(therapist_email: str = "therapist@demo.com") -> None:
    """End any IN_PROGRESS sessions left by earlier tests in the shared CI database."""
    db = SessionLocal()
    try:
        therapist = db.scalars(select(User).where(User.email == therapist_email)).first()
        if not therapist:
            return
        active = db.scalars(
            select(TherapySession).where(
                TherapySession.therapist_user_id == therapist.id,
                TherapySession.status == SessionStatus.IN_PROGRESS,
            )
        ).all()
        for session in active:
            session.actual_start_at = datetime.now(timezone.utc) - timedelta(minutes=6)
            session_service.end_session(db, session)
        if active:
            db.commit()
    finally:
        db.close()


def demo_parent_case_id() -> int | None:
    """Case linked to parent@demo.com in seed data."""
    from app.models.case import Case
    from app.services import parent_service

    db = SessionLocal()
    try:
        parent = db.scalars(select(User).where(User.email == "parent@demo.com")).first()
        if not parent:
            return None
        child_ids = parent_service.child_ids_for_parent(db, parent.id)
        if not child_ids:
            return None
        case = db.scalars(select(Case).where(Case.child_id.in_(child_ids)).limit(1)).first()
        return case.id if case else None
    finally:
        db.close()


def ensure_scheduled_sessions_for_therapist(
    therapist_email: str = "therapist@demo.com",
    *,
    min_count: int = 2,
    days_ahead: int = 14,
    preferred_case_id: int | None = None,
) -> list[int]:
    """
    Guarantee at least ``min_count`` SCHEDULED sessions in the therapist upcoming window.

    Earlier tests often complete the demo seed's scheduled sessions; this creates fresh
    slots on assigned cases when the shared SQLite DB no longer has enough SCHEDULED rows.
    """
    end_active_sessions_for_therapist(therapist_email)
    db = SessionLocal()
    try:
        therapist = db.scalars(select(User).where(User.email == therapist_email)).first()
        if not therapist:
            return []
        assignments = db.scalars(
            select(CaseAssignment).where(
                CaseAssignment.therapist_user_id == therapist.id,
                CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
            )
        ).all()
        case_ids = [a.case_id for a in assignments]
        if preferred_case_id is not None and preferred_case_id in case_ids:
            case_ids = [preferred_case_id] + [cid for cid in case_ids if cid != preferred_case_id]
        if not case_ids:
            return []

        today = date.today()
        window_end = today + timedelta(days=7)
        scheduled = list(
            db.scalars(
                select(TherapySession)
                .where(
                    TherapySession.therapist_user_id == therapist.id,
                    TherapySession.status == SessionStatus.SCHEDULED,
                    TherapySession.scheduled_date >= today,
                    TherapySession.scheduled_date <= window_end,
                )
                .order_by(TherapySession.scheduled_date, TherapySession.start_time)
            ).all()
        )
        if preferred_case_id is not None:
            scheduled = [s for s in scheduled if s.case_id == preferred_case_id]
            case_ids = [preferred_case_id]

        day_offset = 0
        hour = 16
        while len(scheduled) < min_count and day_offset <= days_ahead:
            day = today + timedelta(days=day_offset)
            day_offset += 1
            for case_id in case_ids:
                if len(scheduled) >= min_count:
                    break
                taken = db.scalars(
                    select(TherapySession.id).where(
                        TherapySession.case_id == case_id,
                        TherapySession.scheduled_date == day,
                    )
                ).first()
                if taken:
                    continue
                sess = TherapySession(
                    case_id=case_id,
                    therapist_user_id=therapist.id,
                    scheduled_date=day,
                    start_time=time(hour % 23, 0),
                    end_time=time((hour % 23) + 1, 0),
                    mode=SessionMode.HOME,
                    status=SessionStatus.SCHEDULED,
                )
                db.add(sess)
                db.flush()
                scheduled.append(sess)
                hour += 1

        db.commit()
        return [s.id for s in scheduled[:min_count]]
    finally:
        db.close()
