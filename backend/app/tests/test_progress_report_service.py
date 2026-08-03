"""Progress report reliability — scoped evidence, status rules, refresh, review, parent bridge."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.database import SessionLocal, ensure_sqlite_schema_patches
from app.main import app
from app.models.case import Case
from app.models.clinical_evidence import SessionGoalEntry
from app.models.clinical_report import (
    ClinicalReport,
    ClinicalReportSection,
    ClinicalReportStatus,
    ClinicalReportType,
    ClinicalReportVersion,
)
from app.models.daily_log import AttendanceStatus, DailyLog, LogApprovalStatus
from app.models.session import Session as TherapySession
from app.models.session import SessionStatus
from app.models.user import User
from app.services import (
    parent_canonical_report_service,
    progress_evidence_scope_service as scope_svc,
    progress_report_service as progress_svc,
    progress_review_service,
    progress_status_rules,
    report_engine_service,
    report_status_service,
)
from app.tests.conftest import api_first_case_id, login_headers

ensure_sqlite_schema_patches()
client = TestClient(app)


def _therapist_cm_parent(db):
    therapist = db.scalar(select(User).where(User.email == "therapist@demo.com"))
    cm = db.scalar(select(User).where(User.email == "casemanager@demo.com"))
    parent = db.scalar(select(User).where(User.email == "parent@demo.com"))
    return therapist, cm, parent


def _start_progress(db, case, therapist):
    report = progress_svc.get_or_create_progress_report(db, case, therapist)
    db.commit()
    return report


def _fill_required_sections(db, report):
    for key in (
        "period_overview",
        "goals_progress",
        "strengths_and_development",
        "strategies_and_supports",
        "challenges_and_support_needs",
        "family_school_input",
        "next_period_plan",
        "parent_summary",
    ):
        report_engine_service.patch_section(
            db,
            report,
            key,
            narrative_text=f"<p>Completed narrative for {key} with enough clinical detail here.</p>",
        )
    db.commit()


def _confirm_goals(db, report, therapist):
    sec = db.scalar(
        select(ClinicalReportSection).where(
            ClinicalReportSection.report_id == report.id,
            ClinicalReportSection.section_key == "goals_progress",
        )
    )
    data = {}
    if sec and sec.structured_data_json:
        import json

        data = json.loads(sec.structured_data_json)
    goals = data.get("goals") or []
    if not goals:
        return
    for g in goals:
        progress_svc.patch_progress_goal(
            db,
            report,
            g.get("goal_id") or "1",
            therapist,
            status_confirmed=True,
        )
    db.commit()


def test_scoped_evidence_excludes_out_of_period_logs():
    with SessionLocal() as db:
        therapist, _, _ = _therapist_cm_parent(db)
        case = db.scalars(select(Case)).first()
        assert case
        period_start = date.today() - timedelta(days=30)
        period_end = date.today()
        scope = scope_svc.EvidenceScope(
            review_period_start=period_start,
            review_period_end=period_end,
            evidence_cutoff_at=datetime.combine(period_end, time(23, 59, 59), tzinfo=timezone.utc),
        )
        session_in = TherapySession(
            case_id=case.id,
            therapist_user_id=therapist.id,
            scheduled_date=period_start + timedelta(days=5),
            status=SessionStatus.COMPLETED,
        )
        session_out = TherapySession(
            case_id=case.id,
            therapist_user_id=therapist.id,
            scheduled_date=period_start - timedelta(days=10),
            status=SessionStatus.COMPLETED,
        )
        db.add_all([session_in, session_out])
        db.flush()
        now = datetime.now(timezone.utc)
        log_in = DailyLog(
            session_id=session_in.id,
            attendance_status=AttendanceStatus.PRESENT,
            submitted_at=now,
            approval_status=LogApprovalStatus.APPROVED.value,
        )
        log_out = DailyLog(
            session_id=session_out.id,
            attendance_status=AttendanceStatus.PRESENT,
            submitted_at=now,
            approval_status=LogApprovalStatus.APPROVED.value,
        )
        db.add_all([log_in, log_out])
        db.commit()
        scoped = scope_svc.list_scoped_approved_logs(db, case.id, scope)
        ids = {log.id for log in scoped}
        assert log_in.id in ids
        assert log_out.id not in ids


def test_scoped_evidence_requires_approved_logs():
    with SessionLocal() as db:
        therapist, _, _ = _therapist_cm_parent(db)
        case = db.scalars(select(Case)).first()
        period_start = date.today() - timedelta(days=7)
        period_end = date.today()
        scope = scope_svc.EvidenceScope(
            review_period_start=period_start,
            review_period_end=period_end,
            evidence_cutoff_at=datetime.now(timezone.utc),
        )
        session = TherapySession(
            case_id=case.id,
            therapist_user_id=therapist.id,
            scheduled_date=period_start,
            status=SessionStatus.COMPLETED,
        )
        db.add(session)
        db.flush()
        pending_log = DailyLog(
            session_id=session.id,
            attendance_status=AttendanceStatus.PRESENT,
            submitted_at=datetime.now(timezone.utc),
            approval_status=LogApprovalStatus.PENDING.value,
        )
        db.add(pending_log)
        db.commit()
        scoped = scope_svc.list_scoped_approved_logs(db, case.id, scope)
        assert pending_log.id not in {log.id for log in scoped}


def test_monthly_overlap_requires_approved_engine_monthly():
    with SessionLocal() as db:
        therapist, cm, _ = _therapist_cm_parent(db)
        case = db.scalars(select(Case)).first()
        draft = report_engine_service.get_or_create_monthly_report(db, case, therapist, "2026-01")
        approved = report_engine_service.get_or_create_monthly_report(db, case, therapist, "2026-02")
        for key in ("child_summary", "sessions_summary", "goals_progress", "next_month_focus", "parent_summary"):
            report_engine_service.patch_section(db, approved, key, narrative_text=f"Done {key} " * 5)
        report_status_service.submit_report(db, approved, therapist, readiness_ok=True)
        report_status_service.approve_report(db, approved, cm, share_parent=False)
        db.commit()
        scope = scope_svc.EvidenceScope(
            review_period_start=date(2026, 1, 1),
            review_period_end=date(2026, 3, 31),
            evidence_cutoff_at=datetime(2026, 3, 31, 23, 59, 59, tzinfo=timezone.utc),
        )
        monthlies = scope_svc.list_scoped_monthly_reports(db, case.id, scope)
        ids = {m.id for m in monthlies}
        assert approved.id in ids
        assert draft.id not in ids


def test_iep_version_pinned_at_populate():
    with SessionLocal() as db:
        therapist, _, _ = _therapist_cm_parent(db)
        case = db.scalars(select(Case)).first()
        report = _start_progress(db, case, therapist)
        progress_svc.populate_progress_from_evidence(db, report)
        db.commit()
        meta1 = progress_svc.get_progress_metadata(report)
        v1 = meta1.get("source_iep_version_id")
        progress_svc.populate_progress_from_evidence(db, report)
        db.commit()
        meta2 = progress_svc.get_progress_metadata(report)
        assert meta2.get("source_iep_version_id") == v1


def test_suggest_goal_status_deterministic():
    status = progress_status_rules.suggest_goal_status({
        "evidence_strength": "moderate",
        "latest_trend": "stable",
        "sessions_addressed": 3,
    })
    assert status == "Building"
    empty = progress_status_rules.suggest_goal_status({
        "evidence_strength": "weak",
        "latest_trend": None,
        "sessions_addressed": 0,
    })
    assert empty == "Not enough evidence"


def test_therapist_override_final_status():
    with SessionLocal() as db:
        therapist, _, _ = _therapist_cm_parent(db)
        case = db.scalars(select(Case)).first()
        report = _start_progress(db, case, therapist)
        progress_svc.populate_progress_from_evidence(db, report)
        sec = db.scalar(
            select(ClinicalReportSection).where(
                ClinicalReportSection.report_id == report.id,
                ClinicalReportSection.section_key == "goals_progress",
            )
        )
        import json

        data = json.loads(sec.structured_data_json) if sec.structured_data_json else {"goals": []}
        goals = data.get("goals") or []
        if not goals:
            data["goals"] = [{
                "goal_id": "demo-1",
                "label": "Demo goal",
                "suggested_status": "Emerging",
                "sessions_addressed": 1,
            }]
            sec.structured_data_json = json.dumps(data)
            db.commit()
            goals = data["goals"]
        goal_id = goals[0].get("goal_id") or "demo-1"
        progress_svc.patch_progress_goal(
            db,
            report,
            goal_id,
            therapist,
            final_status="Consistent",
            final_summary="Therapist confirmed consistent progress.",
        )
        db.commit()
        sec = db.scalar(
            select(ClinicalReportSection).where(
                ClinicalReportSection.report_id == report.id,
                ClinicalReportSection.section_key == "goals_progress",
            )
        )
        updated = json.loads(sec.structured_data_json)["goals"][0]
        assert updated["final_status"] == "Consistent"
        assert progress_status_rules.effective_goal_status(updated) == "Consistent"


def test_refresh_skips_therapist_edited_sections():
    with SessionLocal() as db:
        therapist, _, _ = _therapist_cm_parent(db)
        case = db.scalars(select(Case)).first()
        report = _start_progress(db, case, therapist)
        progress_svc.populate_progress_from_evidence(db, report)
        custom = "<p>Therapist edited strengths narrative stays.</p>"
        progress_svc.patch_progress_section(
            db,
            report,
            "strengths_and_development",
            therapist,
            narrative_text=custom,
        )
        db.commit()
        result = progress_svc.refresh_progress_evidence(db, report)
        skipped = [p for p in result["refresh_preview"] if p["section_key"] == "strengths_and_development"]
        assert skipped and skipped[0]["skipped_reason"]
        sec = db.scalar(
            select(ClinicalReportSection).where(
                ClinicalReportSection.report_id == report.id,
                ClinicalReportSection.section_key == "strengths_and_development",
            )
        )
        assert custom in (sec.narrative_text or "")


def test_duplicate_active_progress_prevented():
    with SessionLocal() as db:
        therapist, _, _ = _therapist_cm_parent(db)
        case = db.scalars(select(Case)).first()
        _start_progress(db, case, therapist)
        try:
            progress_svc.start_next_cycle(db, case, therapist)
            raised = False
        except ValueError:
            raised = True
        assert raised


def test_cm_return_and_resubmit_flow():
    with SessionLocal() as db:
        therapist, cm, _ = _therapist_cm_parent(db)
        case = db.scalars(select(Case)).first()
        report = _start_progress(db, case, therapist)
        progress_svc.populate_progress_from_evidence(db, report)
        _fill_required_sections(db, report)
        _confirm_goals(db, report, therapist)
        report_status_service.submit_report(db, report, therapist, readiness_ok=True)
        progress_review_service.return_with_comments(
            db, report, cm, "Please expand parent summary", section_comments={"parent_summary": "Add family voice"}
        )
        report_status_service.submit_report(db, report, therapist, readiness_ok=True)
        db.commit()
        events = progress_review_service.list_review_thread(db, report.id)
        submitted = [e for e in events if e["event_type"] == "submitted"]
        assert len(submitted) >= 2


def test_approval_immutability():
    with SessionLocal() as db:
        therapist, cm, _ = _therapist_cm_parent(db)
        case = db.scalars(select(Case)).first()
        report = _start_progress(db, case, therapist)
        progress_svc.populate_progress_from_evidence(db, report)
        _fill_required_sections(db, report)
        _confirm_goals(db, report, therapist)
        report_status_service.submit_report(db, report, therapist, readiness_ok=True)
        report_status_service.approve_report(db, report, cm, share_parent=False)
        db.commit()
        assert report.current_version_id is not None
        try:
            progress_svc.populate_progress_from_evidence(db, report)
            blocked = False
        except ValueError:
            blocked = True
        assert blocked
        assert report_status_service.can_therapist_edit(report, therapist) is False


def test_correction_creates_new_report_row():
    with SessionLocal() as db:
        therapist, cm, _ = _therapist_cm_parent(db)
        case = db.scalars(select(Case)).first()
        locked = _start_progress(db, case, therapist)
        _fill_required_sections(db, locked)
        _confirm_goals(db, locked, therapist)
        report_status_service.submit_report(db, locked, therapist, readiness_ok=True)
        report_status_service.approve_report(db, locked, cm, share_parent=False)
        db.commit()
        snap_before = db.get(ClinicalReportVersion, locked.current_version_id)
        snap_json_before = snap_before.snapshot_json
        correction = progress_svc.start_correction_cycle(db, case, therapist, locked_report_id=locked.id)
        progress_svc.patch_progress_section(
            db,
            correction,
            "parent_summary",
            therapist,
            narrative_text="<p>Correction draft parent summary with more detail added here.</p>",
        )
        db.commit()
        snap_after = db.get(ClinicalReportVersion, locked.current_version_id)
        assert correction.id != locked.id
        assert snap_after.snapshot_json == snap_json_before


def test_parent_serializer_strips_internal_fields():
    with SessionLocal() as db:
        therapist, cm, parent = _therapist_cm_parent(db)
        case = db.scalars(select(Case)).first()
        report = _start_progress(db, case, therapist)
        progress_svc.populate_progress_from_evidence(db, report)
        _fill_required_sections(db, report)
        _confirm_goals(db, report, therapist)
        report_status_service.submit_report(db, report, therapist, readiness_ok=True)
        report_status_service.approve_report(db, report, cm, share_parent=True)
        db.commit()
        safe = progress_svc.serialize_parent_safe_progress(db, report, case)
        payload = str(safe)
        assert "suggested_status" not in payload
        assert "evidence_summary" not in payload
        assert "therapist_reflection" not in payload


def test_parent_cannot_see_draft_progress():
    with SessionLocal() as db:
        therapist, _, parent = _therapist_cm_parent(db)
        case = db.scalars(select(Case)).first()
        report = _start_progress(db, case, therapist)
        db.commit()
        detail = parent_canonical_report_service.get_clinical_progress_for_parent(db, parent, report.id)
        assert detail is None


def test_permissions_therapist_cm_parent():
    therapist_headers = login_headers(client, "therapist@demo.com")
    case_id = api_first_case_id(client, therapist_headers)
    start = client.post(f"/api/v1/cases/{case_id}/reports/progress/start", headers=therapist_headers)
    assert start.status_code == 200
    report_id = start.json()["report_id"]
    populate = client.post(
        f"/api/v1/reports/{report_id}/progress/populate-from-evidence",
        headers=therapist_headers,
    )
    assert populate.status_code == 200
    parent_headers = login_headers(client, "parent@demo.com")
    preview_parent = client.get(f"/api/v1/reports/{report_id}/preview?mode=parent", headers=parent_headers)
    assert preview_parent.status_code in (403, 404, 400)
    thread = client.get(f"/api/v1/reports/{report_id}/progress/review-thread", headers=therapist_headers)
    assert thread.status_code == 200
