"""Tests for SessionLogApplicationService and evidence projection."""

from __future__ import annotations

import json

import pytest

from app.schemas.structured_session_evidence import StructuredSessionEvidence
from app.services import session_log_application_service as sla


def test_validate_rejects_pending_iep_goal():
    model = StructuredSessionEvidence(
        session_id=1,
        todays_story="Worked on communication.",
        goals=[
            {
                "goal_label": "Turn-taking",
                "match_type": "active_iep",
                "status": "pending",
            }
        ],
    )
    with pytest.raises(sla.SessionLogValidationError, match="Confirm or reject"):
        sla.validate_structured_for_submit(model)


def test_validate_accepts_confirmed_goal_without_story():
    model = StructuredSessionEvidence(
        session_id=1,
        goals=[
            {
                "goal_label": "Turn-taking",
                "match_type": "active_iep",
                "status": "confirmed",
            }
        ],
    )
    sla.validate_structured_for_submit(model)


def test_evidence_payload_to_structured_maps_goals():
    from app.models.daily_log import DailyLog

    log = DailyLog(session_id=1, activities_done="legacy")
    structured = sla.evidence_payload_to_structured(
        log,
        goals=[{"goal_label": "Social play", "goal_card_id": 5, "measurement_note": "2 turns"}],
        strategies=[],
    )
    assert structured.goals[0].goal_label == "Social play"
    assert structured.goals[0].status == "confirmed"


def test_build_projection_from_structured():
    from sqlalchemy import select

    from app.core.database import SessionLocal, ensure_sqlite_schema_patches
    from app.models.daily_log import AttendanceStatus, DailyLog, LogApprovalStatus
    from app.models.session import Session as TherapySession
    from app.models.user import User
    from app.services import session_evidence_projection_service as sep_svc
    from app.services import structured_session_log_service as sse_svc

    ensure_sqlite_schema_patches()
    with SessionLocal() as db:
        session = None
        log = None
        for s in db.scalars(select(TherapySession)).all():
            candidate = db.scalars(select(DailyLog).where(DailyLog.session_id == s.id)).first()
            if candidate and candidate.approval_status != LogApprovalStatus.APPROVED:
                session, log = s, candidate
                break
            if not candidate:
                session = s
                log = DailyLog(
                    session_id=s.id,
                    attendance_status=AttendanceStatus.PRESENT,
                    activities_done="Story",
                    approval_status=LogApprovalStatus.PENDING,
                )
                db.add(log)
                db.commit()
                db.refresh(log)
                break
        if not session or not log:
            pytest.skip("No editable daily log fixture")
        user = db.scalars(select(User)).first()
        structured = StructuredSessionEvidence(
            session_id=session.id,
            todays_story="Child engaged in turn-taking.",
            child_response_signals=["engaged"],
            goals=[
                {
                    "goal_label": "Turn-taking",
                    "match_type": "active_iep",
                    "status": "confirmed",
                    "evidence": ["Took two turns"],
                }
            ],
        )
        sse_svc.apply_structured_session_to_log(db, log, user, structured)
        db.commit()
        db.refresh(log)

        proj = sep_svc.build_session_evidence_projection(db, log)
        assert proj.session_story == "Child engaged in turn-taking."
        assert proj.child_response_signals == ["engaged"]
        assert len(proj.confirmed_goal_evidence) >= 1
