"""Tests for session goal entries and dual-write to goals_addressed."""

from __future__ import annotations

from sqlalchemy import select

from app.core.database import SessionLocal, ensure_sqlite_schema_patches
from app.models.daily_log import DailyLog
from app.models.session import Session as TherapySession
from app.services import clinical_evidence_service as ev_svc

ensure_sqlite_schema_patches()


def test_session_goal_entries_save_and_dual_write():
    with SessionLocal() as db:
        session = db.scalars(select(TherapySession).limit(1)).first()
        assert session is not None
        log = db.scalars(select(DailyLog).where(DailyLog.session_id == session.id)).first()
        if not log:
            log = DailyLog(session_id=session.id, activities_done="test", goals_addressed="")
            db.add(log)
            db.commit()
            db.refresh(log)

        ev_svc.save_session_evidence(
            db,
            daily_log=log,
            case_id=session.case_id,
            goals=[
                {
                    "goal_label": "Used visual schedule",
                    "support_level": "MODERATE",
                    "response_note": "Calmer transitions",
                }
            ],
            strategies=[{"strategy_label": "First-then board", "outcome_note": "Helpful"}],
        )
        db.refresh(log)
        assert "Used visual schedule" in (log.goals_addressed or "")
        payload = ev_svc.entries_for_log(db, log.id)
        assert len(payload["goals"]) == 1
        assert payload["goals"][0]["support_level"] == "MODERATE"
