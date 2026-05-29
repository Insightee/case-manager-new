"""Generate monthly report draft from submitted session logs."""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.database import SessionLocal
from app.main import app
from app.models.assignment import CaseAssignment, CaseAssignmentStatus
from app.models.case import Case
from app.models.daily_log import DailyLog, LogApprovalStatus
from app.models.report import MonthlyReport, ReportStatus
from app.models.session import Session as TherapySession
from app.models.session import SessionStatus
from app.models.user import User
from app.seed.demo_seed import run as seed_run
from app.tests.conftest import api_items

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    seed_run()


def _login(email: str) -> dict:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "demo123"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _therapist_case_and_session(db) -> tuple[int, int, User]:
    therapist = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
    assignment = db.scalars(
        select(CaseAssignment).where(
            CaseAssignment.therapist_user_id == therapist.id,
            CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
        )
    ).first()
    assert assignment
    case_id = assignment.case_id
    session = TherapySession(
        case_id=case_id,
        therapist_user_id=therapist.id,
        scheduled_date=date(2026, 5, 15),
        status=SessionStatus.COMPLETED,
    )
    db.add(session)
    db.flush()
    return case_id, session.id, therapist


def test_generate_from_logs_includes_pending_and_approved():
    db = SessionLocal()
    try:
        case_id, session_id, therapist = _therapist_case_and_session(db)
        pending_log = DailyLog(
            session_id=session_id,
            attendance_status="PRESENT",
            activities_done="Worked on communication goals",
            goals_addressed="Turn-taking",
            parent_notes="Good session at home",
            submitted_at=datetime.now(timezone.utc),
            approval_status=LogApprovalStatus.PENDING,
        )
        db.add(pending_log)
        db.flush()

        report = MonthlyReport(
            case_id=case_id,
            therapist_user_id=therapist.id,
            month="May 2026",
            status=ReportStatus.DRAFT,
        )
        db.add(report)
        db.commit()
        db.refresh(report)
        report_id = report.id
    finally:
        db.close()

    headers = _login("therapist@demo.com")
    ctx = client.get(f"/api/v1/reports/monthly/{report_id}/session-context", headers=headers)
    assert ctx.status_code == 200
    ctx_rows = ctx.json()
    assert len(ctx_rows) >= 1
    assert any(r["approval_status"] == "PENDING" for r in ctx_rows)

    gen = client.post(
        f"/api/v1/reports/monthly/{report_id}/generate-from-logs",
        headers=headers,
        json={"mode": "replace"},
    )
    assert gen.status_code == 200, gen.text
    body = gen.json()
    assert "communication goals" in (body.get("body_html") or "")
    assert "Pending admin review" in (body.get("body_html") or "")


def test_generate_from_logs_rejects_non_author():
    headers = _login("therapist@demo.com")
    other_headers = _login("parent@demo.com")
    cases = client.get("/api/v1/cases", headers=headers)
    case_id = api_items(cases.json())[0]["id"]
    created = client.post(
        "/api/v1/reports/monthly",
        headers=headers,
        json={"case_id": case_id, "month": "Compile Auth 2099"},
    )
    assert created.status_code == 201
    rid = created.json()["id"]
    gen = client.post(
        f"/api/v1/reports/monthly/{rid}/generate-from-logs",
        headers=other_headers,
        json={"mode": "replace"},
    )
    assert gen.status_code in (403, 404)


def test_compile_service_excludes_rejected_logs():
    db = SessionLocal()
    try:
        case_id, session_id, therapist = _therapist_case_and_session(db)
        rejected_session = TherapySession(
            case_id=case_id,
            therapist_user_id=therapist.id,
            scheduled_date=date(2026, 5, 20),
            status=SessionStatus.COMPLETED,
        )
        db.add(rejected_session)
        db.flush()
        db.add(
            DailyLog(
                session_id=rejected_session.id,
                attendance_status="PRESENT",
                activities_done="Should not appear",
                submitted_at=datetime.now(timezone.utc),
                approval_status=LogApprovalStatus.REJECTED,
            )
        )
        report = MonthlyReport(
            case_id=case_id,
            therapist_user_id=therapist.id,
            month="May 2026",
            status=ReportStatus.DRAFT,
        )
        db.add(report)
        db.commit()
        db.refresh(report)
        from app.services.report_compile_service import compile_body_html_from_logs
        from app.services.report_log_query import submitted_logs_for_report_month

        logs = submitted_logs_for_report_month(db, report)
        html = compile_body_html_from_logs(logs)
        assert "Should not appear" not in html
    finally:
        db.close()
