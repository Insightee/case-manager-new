"""Tests for session goal entries and dual-write to goals_addressed."""

from __future__ import annotations

from sqlalchemy import select

from app.core.database import SessionLocal, ensure_sqlite_schema_patches
from app.models.daily_log import AttendanceStatus, DailyLog, LogApprovalStatus
from app.models.session import Session as TherapySession
from app.services import clinical_evidence_service as ev_svc

ensure_sqlite_schema_patches()


def _editable_log(db, session):
    log = db.scalars(select(DailyLog).where(DailyLog.session_id == session.id)).first()
    if log:
        if log.approval_status == LogApprovalStatus.APPROVED:
            return None
        return log
    log = DailyLog(
        session_id=session.id,
        attendance_status=AttendanceStatus.PRESENT,
        activities_done="test",
        goals_addressed="",
        approval_status=LogApprovalStatus.PENDING,
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


def _any_editable_log(db):
    sessions = db.scalars(select(TherapySession)).all()
    for session in sessions:
        log = _editable_log(db, session)
        if log:
            return session, log
    raise AssertionError("No editable daily log fixture available")


def test_session_goal_entries_save_and_dual_write():
    with SessionLocal() as db:
        session, log = _any_editable_log(db)

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
        assert payload["schema_version"] == 1


def test_session_goal_entries_v2_scores_persist():
    with SessionLocal() as db:
        session, log = _any_editable_log(db)
        log.activities_done = "v2 test"
        log.goals_addressed = ""
        db.commit()
        db.refresh(log)

        ev_svc.save_session_evidence(
            db,
            daily_log=log,
            case_id=session.case_id,
            goals=[
                {
                    "goal_label": "Transition support",
                    "participation_score": 3,
                    "independence_score": 2,
                    "goal_achievement_score": 3,
                    "activity_used": "Visual schedule",
                    "strategies": [
                        {
                            "strategy_label": "First-then board",
                            "strategy_feedback": "HELPFUL",
                        }
                    ],
                }
            ],
            strategies=[],
        )
        payload = ev_svc.entries_for_log(db, log.id)
        assert payload["schema_version"] == 2
        g = payload["goals"][0]
        assert g["participation_score"] == 3
        assert g["support_level"] is None
        assert g["strategies"][0]["strategy_feedback"] == "HELPFUL"


def test_legacy_log_unchanged_when_no_evidence_payload():
    """Text-only PATCH must not require or mutate structured evidence."""
    with SessionLocal() as db:
        session, log = _any_editable_log(db)
        log.activities_done = "before"
        log.goals_addressed = "Legacy goal text"
        db.commit()
        db.refresh(log)

        ev_svc.save_session_evidence(
            db,
            daily_log=log,
            case_id=session.case_id,
            goals=[{"goal_label": "Legacy goal", "support_level": "MINIMUM", "response_note": "ok"}],
            strategies=[],
        )
        before = ev_svc.entries_for_log(db, log.id)
        assert before["schema_version"] == 1

        log.activities_done = "after text edit"
        db.commit()

        after = ev_svc.entries_for_log(db, log.id)
        assert after["schema_version"] == 1
        assert after["goals"][0]["support_level"] == "MINIMUM"
        assert log.activities_done == "after text edit"
