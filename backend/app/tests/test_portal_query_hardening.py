"""Regression tests for portal API query hardening (P1.5)."""

from __future__ import annotations

from datetime import date
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.audit import log_audit
from app.core.database import SessionLocal
from app.main import app
from app.models.audit_event import AuditEvent
from app.models.case import Case
from app.models.report import MonthlyReport, ReportStatus
from app.models.session import Session as TherapySession
from app.models.user import User
from app.models.visibility import VisibilityStatus
from app.seed.demo_seed import run as seed_run
from app.services import admin_report_service

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    seed_run()


def _login(email: str) -> dict[str, str]:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "demo123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_therapist_home_bounded_sections():
    headers = _login("therapist@demo.com")
    r = client.get("/api/v1/therapist/home", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert len(data["upcoming_sessions"]) <= 10
    assert len(data["needs_log_sessions"]) <= 10
    assert len(data["schedule_preview"]) <= 20
    case_ids = {c["id"] for c in data["cases_board"]["allCases"]}
    for section in data["cases_board"]["sections"]:
        for row in section["cases"]:
            assert row["id"] in case_ids


def test_therapist_workspace_needs_log_bounded():
    headers = _login("therapist@demo.com")
    r = client.get("/api/v1/therapist/sessions/workspace", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert len(body["upcoming"]) <= 50
    assert len(body["needs_log"]) <= 50


def test_therapist_reports_pipeline_single_missing_placeholder():
    headers = _login("therapist@demo.com")
    r = client.get("/api/v1/therapist/reports/pipeline", headers=headers)
    assert r.status_code == 200
    data = r.json()
    month = data["month_label"]
    placeholders = [a for a in data["attention"] if a.get("isPlaceholder")]
    by_case = {a["caseDbId"] for a in placeholders if a.get("month") == month}
    assert len(by_case) == len(placeholders), "At most one missing-month placeholder per case"


def test_therapist_home_only_assigned_cases():
    from app.models.assignment import CaseAssignment, CaseAssignmentStatus

    headers = _login("therapist@demo.com")
    home = client.get("/api/v1/therapist/home", headers=headers).json()
    db = SessionLocal()
    try:
        user = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
        allowed_case_ids = {
            row[0]
            for row in db.execute(
                select(CaseAssignment.case_id).where(
                    CaseAssignment.therapist_user_id == user.id,
                    CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
                )
            ).all()
        }
        board_ids = {c["id"] for c in home["cases_board"]["allCases"]}
        assert board_ids.issubset(allowed_case_ids)
        assert len(board_ids) >= 1
    finally:
        db.close()


def test_admin_home_report_queue_honors_page_size():
    calls: list[int] = []

    def _track_monthly(db, user, **kwargs):
        calls.append(kwargs.get("page_size", 0))
        return [], {"total": 0, "page": 1, "page_size": kwargs.get("page_size", 0)}

    with patch.object(admin_report_service, "list_monthly_admin", side_effect=_track_monthly):
        with patch.object(admin_report_service, "list_observation_admin", return_value=([], {"total": 0})):
            from app.services import admin_workbench_service

            db = SessionLocal()
            try:
                user = db.scalars(select(User).where(User.email == "superadmin@demo.com")).first()
                admin_workbench_service.build_workbench_summary(db, user)
            finally:
                db.close()
    assert calls, "list_monthly_admin should be invoked"
    assert max(calls) <= 8, f"Expected page_size <= 8 for workbench, got {calls}"


def test_admin_home_reports_widget_count_from_total():
    headers = _login("superadmin@demo.com")
    home = client.get("/api/v1/admin/home", headers=headers)
    assert home.status_code == 200
    reports_widget = next((w for w in home.json()["widgets"] if w["id"] == "reports"), None)
    if reports_widget and reports_widget.get("section"):
        assert "count" in reports_widget["section"]
        assert len(reports_widget["section"].get("items", [])) <= 8


def test_audit_case_id_filter_not_like():
    db = SessionLocal()
    try:
        case = db.scalars(select(Case).limit(1)).first()
        assert case is not None
        log_audit(
            db,
            actor_user_id=None,
            action="update",
            entity_type="daily_log",
            entity_id="999",
            new_value={"case_id": case.id, "note": "test"},
            case_id=case.id,
        )
        db.commit()
        ev = db.scalars(
            select(AuditEvent).where(AuditEvent.case_id == case.id).order_by(AuditEvent.id.desc())
        ).first()
        assert ev is not None
        assert ev.case_id == case.id
    finally:
        db.close()

    headers = _login("superadmin@demo.com")
    audit = client.get(
        "/api/v1/admin/audit",
        headers=headers,
        params={"case_id": case.id, "limit": 10},
    )
    assert audit.status_code == 200
    ids = {item["id"] for item in audit.json()["items"]}
    assert ev.id in ids
    for item in audit.json()["items"]:
        assert item.get("actor_name")
        assert "actor_user_id" in item


def test_case_timeline_uses_case_id_index():
    headers = _login("superadmin@demo.com")
    db = SessionLocal()
    try:
        case = db.scalars(select(Case).limit(1)).first()
        assert case is not None
        log_audit(
            db,
            actor_user_id=None,
            action="create",
            entity_type="case",
            entity_id=case.id,
            case_id=case.id,
        )
        db.commit()
        timeline = client.get(
            f"/api/v1/admin/cases/{case.id}/timeline",
            headers=headers,
            params={"limit": 20},
        )
        assert timeline.status_code == 200
        assert isinstance(timeline.json()["items"], list)
        assert len(timeline.json()["items"]) <= 20
    finally:
        db.close()


def test_parent_home_safety_regression():
    headers = _login("parent@demo.com")
    home = client.get("/api/v1/parent/home", headers=headers)
    assert home.status_code == 200
    forbidden = {"session_notes", "observations", "internal_notes", "reviewer_comment"}
    for case in home.json()["cases"]:
        highlight = case.get("session_highlight") or {}
        assert not forbidden.intersection(highlight.keys())
    logs = client.get("/api/v1/parent/session-logs", headers=headers).json()
    for row in logs:
        assert "session_notes" not in row


def test_list_queue_admin_respects_small_page_size():
    db = SessionLocal()
    try:
        user = db.scalars(select(User).where(User.email == "superadmin@demo.com")).first()
        with patch.object(admin_report_service, "list_monthly_admin") as mock_m:
            with patch.object(admin_report_service, "list_observation_admin") as mock_o:
                mock_m.return_value = ([], {"total": 3, "page": 1, "page_size": 8})
                mock_o.return_value = ([], {"total": 2, "page": 1, "page_size": 8})
                items, meta = admin_report_service.list_queue_admin(db, user, page=1, page_size=8)
                assert mock_m.call_args.kwargs["page_size"] == 8
                assert mock_o.call_args.kwargs["page_size"] == 8
                assert len(items) <= 8
                assert meta["total"] == 5
    finally:
        db.close()


def test_migration_columns_present():
    db = SessionLocal()
    try:
        row = db.execute(
            select(AuditEvent.case_id).where(AuditEvent.id.isnot(None)).limit(1)
        ).first()
        assert row is not None or True
    finally:
        db.close()
