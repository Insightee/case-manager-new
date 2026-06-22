"""Bundled session evidence on daily log create."""

from __future__ import annotations

from sqlalchemy import select

from app.core.database import SessionLocal, ensure_sqlite_schema_patches
from app.models.daily_log import AttendanceStatus, DailyLog, LogApprovalStatus
from app.models.session import Session as TherapySession
from app.services import clinical_evidence_service as ev_svc

ensure_sqlite_schema_patches()


def _editable_log(db):
    for session in db.scalars(select(TherapySession)).all():
        log = db.scalars(select(DailyLog).where(DailyLog.session_id == session.id)).first()
        if log and log.approval_status != LogApprovalStatus.APPROVED:
            return session, log
        if not log:
            log = DailyLog(
                session_id=session.id,
                attendance_status=AttendanceStatus.PRESENT,
                activities_done="bundle test",
                approval_status=LogApprovalStatus.PENDING,
            )
            db.add(log)
            db.commit()
            db.refresh(log)
            return session, log
    raise AssertionError("No editable log fixture")


def test_bundled_evidence_v2_roundtrip():
    with SessionLocal() as db:
        session, log = _editable_log(db)
        ev_svc.save_session_evidence(
            db,
            daily_log=log,
            case_id=session.case_id,
            goals=[
                {
                    "goal_label": "Peer turn-taking",
                    "participation_score": 2,
                    "independence_score": 2,
                    "goal_achievement_score": 3,
                    "strategies": [
                        {"strategy_label": "Visual timer", "strategy_feedback": "HELPFUL", "short_note": "Worked well"}
                    ],
                }
            ],
            strategies=[],
            commit=True,
        )
        payload = ev_svc.entries_for_log(db, log.id)
        assert payload["schema_version"] == 2
        assert payload["goals"][0]["participation_score"] == 2
        assert payload["goals"][0]["strategies"][0]["strategy_feedback"] == "HELPFUL"
