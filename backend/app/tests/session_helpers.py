"""Test helpers for therapist session start/end flows."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.core.database import SessionLocal
from app.models.session import Session as TherapySession


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
