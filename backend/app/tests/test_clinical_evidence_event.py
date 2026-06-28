"""Tests for Clinical Evidence Event Contract materializer (Pass 1)."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.database import SessionLocal, ensure_sqlite_schema_patches
from app.main import app
from app.models.ai_generation import AiDraftOutput, AiGenerationLog
from app.models.daily_log import AttendanceStatus, DailyLog, LogApprovalStatus
from app.models.session import Session as TherapySession
from app.services import clinical_brain_evidence_service, clinical_evidence_event_service as cee_svc
from app.services import clinical_evidence_service as ev_svc
from app.tests.conftest import login_headers

ensure_sqlite_schema_patches()
client = TestClient(app)


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


def _save_goal_and_strategy(db, log, case_id):
    ev_svc.save_session_evidence(
        db,
        daily_log=log,
        case_id=case_id,
        goals=[
            {
                "goal_label": "Classroom transition",
                "participation_score": 3,
                "independence_score": 2,
                "goal_achievement_score": 3,
                "activity_used": "Visual schedule",
                "participation": "participates_with_support",
                "strategies": [
                    {
                        "strategy_label": "Visual countdown",
                        "strategy_feedback": "HELPFUL",
                        "environment": "SCHOOL",
                        "activity_used": "Transition routine",
                    }
                ],
            }
        ],
        strategies=[],
        commit=True,
    )
    db.refresh(log)


def test_materialize_from_log_goal_and_strategy():
    with SessionLocal() as db:
        session, log = _any_editable_log(db)
        _save_goal_and_strategy(db, log, session.case_id)

        events = cee_svc.materialize_from_log(db, log.id)
        assert len(events) >= 1
        event = events[0]
        assert event["contract_version"] == "1.1.0"
        assert event["identity"]["daily_log_id"] == log.id
        assert event["identity"]["goal_entry_id"] is not None
        assert event["goal_linkage"]["goal_title"] == "Classroom transition"
        assert event["strategy_linkage"]["strategy_feedback"] == "HELPFUL"
        assert event["support_and_response"]["participation_signal"] == "active_with_support"
        assert event["support_and_response"]["child_response"] is None
        assert event["context"]["environment_fit"] is None


def test_materializer_reads_clinical_extension_json():
    with SessionLocal() as db:
        session, log = _any_editable_log(db)
        ev_svc.save_session_evidence(
            db,
            daily_log=log,
            case_id=session.case_id,
            goals=[
                {
                    "goal_label": "Snack routine",
                    "participation_score": 3,
                    "clinical_extension": {
                        "child_response": "accepted",
                        "therapist_interpretation": "continue_with_adaptation",
                        "participation_quality": "participated_with_support",
                        "support_needed": "visual_support",
                        "goal_movement": "small_movement",
                        "strategy_status": "adapted_today",
                        "adaptation_type": ["time_extended"],
                    },
                    "strategies": [
                        {
                            "strategy_label": "First-then board",
                            "strategy_feedback": "PARTLY_HELPFUL",
                            "clinical_extension": {
                                "strategy_status": "adapted_today",
                                "adaptation_type": ["choice_added"],
                            },
                        }
                    ],
                }
            ],
            strategies=[],
            commit=True,
        )
        db.refresh(log)

        events = cee_svc.materialize_from_log(db, log.id)
        assert events
        event = events[0]
        assert event["support_and_response"]["child_response"] == "accepted"
        assert event["context"]["environment_fit"] is None
        assert event["therapist_view"]["therapist_interpretation"] == "continue_with_adaptation"
        assert event["strategy_linkage"].get("adaptation_type") == ["choice_added"]
        prov = event.get("provenance", {}).get("field_provenance", {})
        assert prov.get("child_response") == "human_selected"


def test_v11_quick_evidence_fields_save_and_materialize():
    with SessionLocal() as db:
        session, log = _any_editable_log(db)
        ev_svc.save_session_evidence(
            db,
            daily_log=log,
            case_id=session.case_id,
            goals=[
                {
                    "goal_label": "Peer play initiation",
                    "participation": "participates_with_support",
                    "clinical_extension": {
                        "child_response": "needed_more_time",
                        "participation_quality": "brief_engagement",
                        "environment_fit": "barrier_present",
                        "barrier_type": ["sensory_load", "transition_pressure"],
                        "therapist_interpretation": "continue_with_adaptation",
                        "adaptation_type": ["time_extended"],
                        "adaptation_note": "Extended wait before joining peers",
                        "field_provenance": {
                            "child_response": "human_selected",
                            "adaptation_note": "human_written",
                        },
                    },
                    "strategies": [
                        {
                            "strategy_label": "Visual invitation",
                            "strategy_feedback": "PARTLY_HELPFUL",
                        }
                    ],
                }
            ],
            strategies=[],
            commit=True,
        )
        events = cee_svc.materialize_from_log(db, log.id)
        assert events
        event = events[0]
        assert event["support_and_response"]["child_response"] == "needed_more_time"
        assert event["support_and_response"]["participation_quality"] == "brief_engagement"
        assert event["context"]["environment_fit"] == "barrier_present"
        assert event["context"]["barrier_type"] == ["sensory_load", "transition_pressure"]
        assert event["therapist_view"]["therapist_interpretation"] == "continue_with_adaptation"
        assert event["strategy_linkage"]["adaptation_type"] == ["time_extended"]
        assert event["strategy_linkage"]["adaptation_note"] == "Extended wait before joining peers"
        prov = event.get("provenance", {}).get("field_provenance", {})
        assert prov.get("barrier_type") == "human_selected"
        assert prov.get("adaptation_note") == "human_written"
        assert event["visibility_and_governance"]["parent_visible"] is False


def test_v1_payload_without_clinical_extension_still_saves():
    with SessionLocal() as db:
        session, log = _any_editable_log(db)
        result = ev_svc.save_session_evidence(
            db,
            daily_log=log,
            case_id=session.case_id,
            goals=[
                {
                    "goal_label": "Legacy goal only",
                    "participation_score": 2,
                    "independence_score": 2,
                    "goal_achievement_score": 2,
                }
            ],
            strategies=[],
            commit=True,
        )
        assert result["schema_version"] == 2
        assert result["goals"][0]["goal_label"] == "Legacy goal only"
        assert result["goals"][0].get("clinical_extension") in ({}, None)
        events = cee_svc.materialize_from_log(db, log.id)
        assert events[0]["support_and_response"].get("child_response") is None


def test_evidence_event_id_is_stable_across_rematerialization():
    with SessionLocal() as db:
        session, log = _any_editable_log(db)
        _save_goal_and_strategy(db, log, session.case_id)

        first = cee_svc.materialize_from_log(db, log.id)
        second = cee_svc.materialize_from_log(db, log.id)
        assert first[0]["identity"]["evidence_event_id"] == second[0]["identity"]["evidence_event_id"]


def test_compute_evidence_strength_weak_without_strategy():
    event = {
        "goal_linkage": {"goal_title": "Only goal"},
        "strategy_linkage": {},
        "context": {},
        "support_and_response": {},
    }
    assert cee_svc.compute_evidence_strength(event) == "weak"


def test_compute_evidence_strength_strong_with_feedback():
    event = {
        "goal_linkage": {
            "participation_score": 3,
            "goal_status_participation": "participates_with_support",
        },
        "strategy_linkage": {"strategy_title": "Visual countdown", "strategy_feedback": "HELPFUL"},
        "context": {"activity": "Transition", "environment": "SCHOOL"},
        "support_and_response": {"participation_signal": "active_with_support"},
    }
    assert cee_svc.compute_evidence_strength(event) == "strong"


def test_parent_visible_defaults_false():
    with SessionLocal() as db:
        session, log = _any_editable_log(db)
        _save_goal_and_strategy(db, log, session.case_id)
        events = cee_svc.materialize_from_log(db, log.id)
        for event in events:
            assert event["visibility_and_governance"]["parent_visible"] is False
            assert event["quality"]["evidence_strength_internal_only"] is True


def test_learning_eligibility_custom_strategy_case_specific():
    event = {
        "strategy_linkage": {"is_custom_strategy": True},
        "visibility_and_governance": {"sensitivity_level": "normal"},
    }
    assert cee_svc.compute_learning_eligibility(event) == "case_specific_only"


def test_ai_draft_outputs_are_not_materialized_without_human_acceptance():
    with SessionLocal() as db:
        session, log = _any_editable_log(db)
        log.session_notes = "AI-only prose should not become evidence"
        log.goals_addressed = ""
        db.commit()

        gen = AiGenerationLog(
            user_id=1,
            case_id=session.case_id,
            action="improve_note",
            input_hash="abc123",
        )
        db.add(gen)
        db.flush()
        db.add(
            AiDraftOutput(
                generation_log_id=gen.id,
                target_type="daily_log",
                target_id=log.id,
                draft_text="Child failed transition and was non-compliant",
                accepted=False,
            )
        )
        db.commit()

        events_before = cee_svc.materialize_from_log(db, log.id)
        for event in events_before:
            blob = str(event).lower()
            assert "non-compliant" not in blob
            assert "failed transition" not in blob

        _save_goal_and_strategy(db, log, session.case_id)
        events_after = cee_svc.materialize_from_log(db, log.id)
        assert len(events_after) >= 1
        for event in events_after:
            note = (event.get("therapist_view") or {}).get("therapist_note") or ""
            blob = str(event).lower()
            assert "non-compliant" not in note.lower()
            assert "non-compliant" not in blob
            assert "failed transition" not in blob
        assert cee_svc.ai_draft_outputs_excluded_guardrail()["acceptance_required"] == "true"


def test_api_daily_log_events_rbac():
    therapist_headers = login_headers(client, "therapist@demo.com")

    with SessionLocal() as db:
        session, log = _any_editable_log(db)
        _save_goal_and_strategy(db, log, session.case_id)
        log_id = log.id
        case_id = session.case_id

    ok = client.get(
        f"/api/v1/daily-logs/{log_id}/clinical-evidence-events",
        headers=therapist_headers,
    )
    assert ok.status_code == 200
    body = ok.json()
    assert body["contract_version"] == "1.1.0"
    assert body["rollup"]["event_count"] >= 1

    month_resp = client.get(
        f"/api/v1/cases/{case_id}/clinical-evidence-events",
        params={"month": "2099-01"},
        headers=therapist_headers,
    )
    assert month_resp.status_code == 200

    parent_headers = login_headers(client, "parent@demo.com")
    denied = client.get(
        f"/api/v1/daily-logs/{log_id}/clinical-evidence-events",
        headers=parent_headers,
    )
    assert denied.status_code in (403, 404)


def test_brain_evidence_summary_uses_materializer():
    with SessionLocal() as db:
        from app.models.case import Case
        from app.models.user import User
        from app.services import report_engine_service

        session, log = _any_editable_log(db)
        _save_goal_and_strategy(db, log, session.case_id)
        log.submitted_at = datetime.now(timezone.utc)
        db.commit()

        case = db.get(Case, session.case_id)
        therapist = db.scalar(select(User).where(User.email == "therapist@demo.com"))
        report = report_engine_service.get_or_create_monthly_report(db, case, therapist, "2099-01")
        db.commit()
        db.refresh(report)

        summary = clinical_brain_evidence_service.summarize_report_evidence(db, report)
        assert "materialized_event_count" in summary
        assert "ai_draft_policy" in summary
        assert summary["ai_draft_policy"]["acceptance_required"] == "true"
        assert summary["contract_version"] == "1.1.0"
