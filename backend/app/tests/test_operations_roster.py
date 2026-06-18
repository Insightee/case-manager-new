"""Tests for operations roster exports (therapist + case Excel)."""
from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.database import get_db
from app.main import app
from app.models.assignment import CaseAssignment, CaseAssignmentStatus
from app.models.case import Case, CaseStatus
from app.models.report import MonthlyReport, ReportStatus
from app.models.session import Session as TherapySession
from app.models.session import SessionStatus
from app.models.user import User
from app.services import operations_roster_service


def _login(email: str = "superadmin@demo.com") -> str:
    with TestClient(app) as client:
        r = client.post("/api/v1/auth/login", json={"email": email, "password": "demo123"})
        assert r.status_code == 200, r.text
        return r.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_build_case_rows_includes_core_fields(client: TestClient):
    token = _login()
    db = next(get_db())
    try:
        case = db.scalars(select(Case).where(Case.status == CaseStatus.ACTIVE).limit(1)).first()
        assert case is not None
        ym = operations_roster_service.default_export_month()
        rows = operations_roster_service.build_case_rows(db, db.get(User, 1), month=ym)
        match = [r for r in rows if r["case_id"] == case.id]
        assert match, "Expected seeded active case in roster"
        row = match[0]
        assert row["case_code"] == case.case_code
        assert "product_module" in row
        assert "monthly_report_missing" in row
        assert row["monthly_report_missing"] in ("Y", "N")
        assert "sessions_completed" in row
        assert "iep_status" in row
    finally:
        db.close()


def test_build_therapist_rows_includes_people_fields(client: TestClient):
    token = _login()
    db = next(get_db())
    try:
        admin = db.scalars(select(User).where(User.email == "superadmin@demo.com")).first()
        therapist = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
        assert therapist is not None
        ym = operations_roster_service.default_export_month()
        rows = operations_roster_service.build_therapist_rows(db, admin, month=ym)
        match = [r for r in rows if r["therapist_user_id"] == therapist.id]
        assert match, "Expected demo therapist in roster"
        row = match[0]
        assert row["email"] == "therapist@demo.com"
        assert "active_assignments_count" in row
        assert "primary_cm_name" in row
        assert "monthly_missing_cases" in row
    finally:
        db.close()


def test_case_export_xlsx_endpoint(client: TestClient):
    token = _login()
    ym = operations_roster_service.default_export_month()
    res = client.get(
        f"/api/v1/admin/reports/operations/cases/export.xlsx?month={ym}",
        headers=_auth(token),
    )
    assert res.status_code == 200, res.text
    assert "spreadsheetml" in res.headers.get("content-type", "")
    assert res.content[:2] == b"PK"
    assert f"case-operations-roster-{ym}.xlsx" in res.headers.get("content-disposition", "")


def test_therapist_export_xlsx_endpoint(client: TestClient):
    token = _login()
    ym = operations_roster_service.default_export_month()
    res = client.get(
        f"/api/v1/admin/reports/operations/therapists/export.xlsx?month={ym}",
        headers=_auth(token),
    )
    assert res.status_code == 200, res.text
    assert "spreadsheetml" in res.headers.get("content-type", "")
    assert res.content[:2] == b"PK"


def test_month_filter_changes_session_counts(client: TestClient):
    db = next(get_db())
    try:
        admin = db.scalars(select(User).where(User.email == "superadmin@demo.com")).first()
        case = db.scalars(select(Case).where(Case.status == CaseStatus.ACTIVE).limit(1)).first()
        therapist = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
        assert case and therapist

        assignment = db.scalars(
            select(CaseAssignment).where(
                CaseAssignment.case_id == case.id,
                CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
            )
        ).first()
        if not assignment:
            assignment = CaseAssignment(
                case_id=case.id,
                therapist_user_id=therapist.id,
                status=CaseAssignmentStatus.ACTIVE,
                start_date=date.today(),
            )
            db.add(assignment)
            db.flush()

        session = TherapySession(
            case_id=case.id,
            therapist_user_id=therapist.id,
            scheduled_date=date(2099, 6, 15),
            status=SessionStatus.COMPLETED,
        )
        db.add(session)
        db.commit()

        rows = operations_roster_service.build_case_rows(db, admin, month="2099-06")
        row = next(r for r in rows if r["case_id"] == case.id)
        assert row["sessions_completed"] >= 1
    finally:
        db.close()


def test_therapist_without_reports_permission_forbidden(client: TestClient):
    token = _login("therapist@demo.com")
    res = client.get(
        "/api/v1/admin/reports/operations/cases/export.xlsx",
        headers=_auth(token),
    )
    assert res.status_code == 403
