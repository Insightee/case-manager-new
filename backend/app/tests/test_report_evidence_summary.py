"""Evidence summary for clinical reports (session log counts and recent snippets)."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.database import SessionLocal
from app.main import app
from app.models.assignment import CaseAssignment, CaseAssignmentStatus
from app.models.case import Case, CaseStatus
from app.models.child import Child
from app.models.parent import ParentGuardian
from app.models.clinical_report import ClinicalReport, ClinicalReportStatus, ClinicalReportType
from app.models.daily_log import DailyLog, LogApprovalStatus
from app.models.session import Session as TherapySession
from app.models.session import SessionStatus
from app.models.user import User
from app.services.report_engine_service import seed_observation_sections
from app.tests.conftest import cm_headers_for_case

client = TestClient(app)


def _login(email: str = "therapist@demo.com") -> dict[str, str]:
    res = client.post("/api/v1/auth/login", json={"email": email, "password": "demo123"})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _case_report_and_logs(
    db,
    *,
    session_notes: str | None = None,
    observations: str | None = None,
) -> tuple[int, int]:
    therapist = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
    cm = db.scalars(select(User).where(User.email == "casemanager@demo.com")).first()
    child = db.scalars(select(Child).limit(1)).first()
    assert therapist is not None and child is not None and cm is not None

    case = Case(
        case_code=f"EVD-{uuid.uuid4().hex[:10]}",
        child_id=child.id,
        service_type="Homecare",
        product_module="homecare",
        status=CaseStatus.ACTIVE,
        case_manager_user_id=cm.id,
    )
    db.add(case)
    db.flush()
    db.add(
        CaseAssignment(
            case_id=case.id,
            therapist_user_id=therapist.id,
            status=CaseAssignmentStatus.ACTIVE,
            start_date=date(2026, 1, 1),
        )
    )

    report = ClinicalReport(
        case_id=case.id,
        child_id=child.id,
        report_type=ClinicalReportType.OBSERVATION.value,
        title="Evidence summary fixture",
        status=ClinicalReportStatus.DRAFT.value,
        created_by_id=therapist.id,
        assigned_therapist_id=therapist.id,
    )
    db.add(report)
    db.flush()
    seed_observation_sections(db, report.id)

    session = TherapySession(
        case_id=case.id,
        therapist_user_id=therapist.id,
        scheduled_date=date(2026, 10, 1),
        status=SessionStatus.COMPLETED,
        actual_start_at=datetime(2026, 10, 1, 9, 0, tzinfo=timezone.utc),
        actual_end_at=datetime(2026, 10, 1, 10, 0, tzinfo=timezone.utc),
    )
    db.add(session)
    db.flush()

    log = DailyLog(
        session_id=session.id,
        attendance_status="PRESENT",
        approval_status=LogApprovalStatus.PENDING,
        session_notes=session_notes,
        observations=observations,
    )
    db.add(log)

    parent = db.scalars(select(User).where(User.email == "parent@demo.com")).first()
    assert parent is not None
    pg = db.scalars(select(ParentGuardian).where(ParentGuardian.user_id == parent.id)).first()
    if not pg:
        pg = ParentGuardian(user_id=parent.id)
        db.add(pg)
        db.flush()
    child_row = db.get(Child, child.id)
    if child_row and child_row not in pg.children:
        pg.children.append(child_row)

    db.commit()
    return case.id, report.id


def _get_evidence_summary(report_id: int, headers: dict[str, str]) -> dict:
    res = client.get(f"/api/v1/reports/{report_id}/evidence-summary", headers=headers)
    assert res.status_code == 200, res.text
    return res.json()


def test_evidence_summary_no_session_logs():
    db = SessionLocal()
    try:
        therapist = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
        child = db.scalars(select(Child).limit(1)).first()
        assert therapist is not None and child is not None
        case = Case(
            case_code=f"EVD-NONE-{uuid.uuid4().hex[:8]}",
            child_id=child.id,
            service_type="Homecare",
            product_module="homecare",
            status=CaseStatus.ACTIVE,
        )
        db.add(case)
        db.flush()
        db.add(
            CaseAssignment(
                case_id=case.id,
                therapist_user_id=therapist.id,
                status=CaseAssignmentStatus.ACTIVE,
                start_date=date(2026, 1, 1),
            )
        )
        report = ClinicalReport(
            case_id=case.id,
            child_id=child.id,
            report_type=ClinicalReportType.OBSERVATION.value,
            title="No logs",
            status=ClinicalReportStatus.DRAFT.value,
            created_by_id=therapist.id,
            assigned_therapist_id=therapist.id,
        )
        db.add(report)
        db.flush()
        seed_observation_sections(db, report.id)
        db.commit()
        report_id = report.id
    finally:
        db.close()

    headers = _login()
    res = client.get(f"/api/v1/reports/{report_id}/evidence-summary", headers=headers)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["session_logs"] == 0
    assert body["logs_with_notes"] == 0
    assert body["recent_sessions"] == []


def test_evidence_summary_log_without_narrative():
    db = SessionLocal()
    try:
        _, report_id = _case_report_and_logs(db, session_notes=None, observations=None)
    finally:
        db.close()

    headers = _login()
    res = client.get(f"/api/v1/reports/{report_id}/evidence-summary", headers=headers)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["session_logs"] == 1
    assert body["logs_with_notes"] == 0
    assert len(body["recent_sessions"]) == 1
    row = body["recent_sessions"][0]
    assert row["has_notes"] is False
    assert "narrative not added yet" in row["snippet"].lower()


def test_evidence_summary_log_with_narrative():
    db = SessionLocal()
    try:
        _, report_id = _case_report_and_logs(
            db,
            session_notes="Child used breathing strategy during transition.",
            observations=None,
        )
    finally:
        db.close()

    headers = _login()
    res = client.get(f"/api/v1/reports/{report_id}/evidence-summary", headers=headers)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["session_logs"] == 1
    assert body["logs_with_notes"] == 1
    assert len(body["recent_sessions"]) == 1
    row = body["recent_sessions"][0]
    assert row["has_notes"] is True
    assert "breathing strategy" in row["snippet"]


def test_evidence_summary_therapist_admin_parent_portals_share_endpoint():
    """Therapist builder, CM case workspace, and parent case view all use the same API."""
    db = SessionLocal()
    try:
        case_id, report_id = _case_report_and_logs(
            db,
            session_notes="Shared narrative for portal RBAC test.",
            observations=None,
        )
    finally:
        db.close()

    therapist_body = _get_evidence_summary(report_id, _login("therapist@demo.com"))
    cm_body = _get_evidence_summary(report_id, cm_headers_for_case(client, case_id))
    parent_body = _get_evidence_summary(report_id, _login("parent@demo.com"))

    for body in (therapist_body, cm_body, parent_body):
        assert body["session_logs"] == 1
        assert body["logs_with_notes"] == 1
        assert body["recent_sessions"][0]["has_notes"] is True


def test_observation_insights_and_candidates_with_session_logs():
    """Sibling report drafting paths that read session-log narrative (therapist workspace)."""
    db = SessionLocal()
    try:
        _, report_id = _case_report_and_logs(
            db,
            session_notes="Regulation supported with visual schedule during morning routine.",
            observations=None,
        )
    finally:
        db.close()

    headers = _login("therapist@demo.com")
    insights = client.post(f"/api/v1/reports/{report_id}/observation/generate-insights", headers=headers)
    assert insights.status_code == 200, insights.text
    payload = insights.json()
    assert payload.get("evidence_snippets") or payload.get("suggested_tiles")

    candidates = client.get(f"/api/v1/reports/{report_id}/observation/candidates", headers=headers)
    assert candidates.status_code == 200, candidates.text
