from __future__ import annotations

from datetime import date, time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.main import app
from app.models.assignment import CaseAssignment, CaseAssignmentStatus
from app.models.case import Case
from app.models.session import Session as TherapySession
from app.models.session import SessionStatus
from app.models.user import User
from app.seed.demo_seed import run as seed_run
from app.services import operational_reports_service

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    seed_run()


def _auth_headers(email: str = "hr@demo.com"):
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "demo123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_hr_report_catalog():
    r = client.get("/api/v1/admin/hr-reports/catalog", headers=_auth_headers())
    assert r.status_code == 200
    data = r.json()
    assert "categories" in data
    assert "reports" in data
    keys = {item["key"] for item in data["reports"]}
    assert "bulk-attendance" in keys
    assert "session-log-detail" in keys
    assert "inactive-clients" in keys
    assert "parent-portal-usage" in keys
    assert "incident-reports" in keys


def test_hr_staff_status_report():
    r = client.get("/api/v1/admin/hr-reports/staff-status", headers=_auth_headers())
    assert r.status_code == 200
    data = r.json()
    assert data["count"] >= 1
    assert "Email" in data["rows"][0]


def test_hr_therapist_status_report():
    r = client.get("/api/v1/admin/hr-reports/therapist-status", headers=_auth_headers())
    assert r.status_code == 200
    assert r.json()["count"] >= 0


def test_module_admin_with_user_manage_can_export_hr_reports():
    r = client.get("/api/v1/admin/hr-reports/therapist-status", headers=_auth_headers("admin@demo.com"))
    assert r.status_code == 200
    assert "rows" in r.json()


def test_finance_cannot_export_hr_reports():
    fin = client.post("/api/v1/auth/login", json={"email": "finance@demo.com", "password": "demo123"})
    headers = {"Authorization": f"Bearer {fin.json()['access_token']}"}
    r = client.get("/api/v1/admin/hr-reports/staff-status", headers=headers)
    assert r.status_code == 403


def test_bulk_attendance_report_json():
    r = client.get(
        "/api/v1/admin/hr-reports/bulk-attendance?month=2026-01",
        headers=_auth_headers("superadmin@demo.com"),
    )
    assert r.status_code == 200
    data = r.json()
    assert "rows" in data
    if data["rows"]:
        assert "Case ID" in data["rows"][0]
        assert "Child Name" in data["rows"][0]
        assert "Parent Name" in data["rows"][0]
        assert "Therapist Name" in data["rows"][0]
        assert "Therapist ID" in data["rows"][0]
        assert "Assignment Start" in data["rows"][0]
        assert "Assignment End" in data["rows"][0]
        assert "Client Name" not in data["rows"][0]
        assert "Logs Pending Approval" in data["rows"][0]
        assert "Logs Rejected" in data["rows"][0]
        assert "Parent Cancelled" not in data["rows"][0]
        assert "Monthly Fixed Pay" not in data["rows"][0]


def test_session_monthly_summary_people_columns():
    r = client.get(
        "/api/v1/admin/hr-reports/session-monthly-summary?month=2026-01",
        headers=_auth_headers("superadmin@demo.com"),
    )
    assert r.status_code == 200
    data = r.json()
    assert "rows" in data
    if data["rows"]:
        row = data["rows"][0]
        assert "Case ID" in row
        assert "Child Name" in row
        assert "Parent Name" in row
        assert "Therapist Name" in row
        assert "Therapist ID" in row
        assert "Assignment Start" in row
        assert "Assignment End" in row
        assert "Client Name" not in row


def test_mid_month_reassignment_splits_bulk_and_monthly_rows():
    """Outgoing + incoming therapists in the same month → two dated rows per case."""
    db = SessionLocal()
    try:
        case = db.scalars(select(Case).where(Case.case_code == "IC-2026-041")).first()
        assert case is not None
        outgoing = db.scalars(
            select(CaseAssignment).where(
                CaseAssignment.case_id == case.id,
                CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
            )
        ).first()
        assert outgoing is not None

        incoming = db.scalars(select(User).where(User.email == "split.therapist@demo.com")).first()
        if not incoming:
            incoming = User(
                email="split.therapist@demo.com",
                password_hash=hash_password("demo123"),
                full_name="Split Therapist",
                external_employee_id="SPLIT-1",
            )
            db.add(incoming)
            db.flush()

        month_start = date(2026, 1, 1)
        handoff = date(2026, 1, 15)
        month_end = date(2026, 1, 31)

        outgoing.start_date = month_start
        outgoing.end_date = handoff
        outgoing.status = CaseAssignmentStatus.ENDED

        # Clear any prior leftover from a re-run of this test.
        for old in db.scalars(
            select(CaseAssignment).where(
                CaseAssignment.case_id == case.id,
                CaseAssignment.therapist_user_id == incoming.id,
            )
        ).all():
            db.delete(old)
        db.flush()

        db.add(
            CaseAssignment(
                case_id=case.id,
                therapist_user_id=incoming.id,
                start_date=date(2026, 1, 16),
                end_date=None,
                status=CaseAssignmentStatus.ACTIVE,
            )
        )
        db.add(
            TherapySession(
                case_id=case.id,
                therapist_user_id=outgoing.therapist_user_id,
                scheduled_date=date(2026, 1, 10),
                start_time=time(10, 0),
                end_time=time(11, 0),
                status=SessionStatus.COMPLETED,
            )
        )
        db.add(
            TherapySession(
                case_id=case.id,
                therapist_user_id=incoming.id,
                scheduled_date=date(2026, 1, 20),
                start_time=time(10, 0),
                end_time=time(11, 0),
                status=SessionStatus.COMPLETED,
            )
        )
        db.commit()

        bulk = operational_reports_service.bulk_attendance_rows(db, "2026-01")
        case_rows = [r for r in bulk if r.get("Case ID") in (case.external_case_ref, case.case_code)]
        assert len(case_rows) == 2, case_rows
        starts = sorted(r["Assignment Start"] for r in case_rows)
        ends = sorted(r["Assignment End"] for r in case_rows)
        assert starts == [month_start.isoformat(), date(2026, 1, 16).isoformat()]
        assert ends == [handoff.isoformat(), month_end.isoformat()]
        therapists = {r["Therapist Name"] for r in case_rows}
        assert len(therapists) == 2

        client_rows, _therapist_rows = operational_reports_service.session_monthly_summary_rows(
            db, "2026-01"
        )
        summary_case = [
            r for r in client_rows if r.get("Case ID") in (case.external_case_ref, case.case_code)
        ]
        assert len(summary_case) == 2, summary_case
        assert {r["Assignment Start"] for r in summary_case} == {
            month_start.isoformat(),
            date(2026, 1, 16).isoformat(),
        }
    finally:
        db.close()

def test_session_log_detail_csv():
    r = client.get(
        "/api/v1/admin/hr-reports/session-log-detail?format=csv&date_from=2026-01-01&date_to=2026-12-31",
        headers=_auth_headers("superadmin@demo.com"),
    )
    assert r.status_code == 200
    assert "text/csv" in r.headers.get("content-type", "")
    header = r.text.splitlines()[0]
    assert "Case ID" in header
    assert "Child Name" in header
    assert "Parent Name" in header
    assert "Therapist Name" in header
    assert "Therapist ID" in header
    cd = r.headers.get("content-disposition", "")
    assert "session-log-detail-" in cd
    assert ".csv" in cd


def test_inactive_clients_xlsx():
    r = client.get(
        "/api/v1/admin/hr-reports/inactive-clients?format=xlsx",
        headers=_auth_headers("superadmin@demo.com"),
    )
    assert r.status_code == 200
    assert r.headers.get("content-type", "").startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    cd = r.headers.get("content-disposition", "")
    assert "inactive-clients-" in cd
    assert ".xlsx" in cd


def test_inactive_clients_json_columns():
    r = client.get(
        "/api/v1/admin/hr-reports/inactive-clients",
        headers=_auth_headers("superadmin@demo.com"),
    )
    assert r.status_code == 200
    data = r.json()
    assert "rows" in data
    if data["rows"]:
        row = data["rows"][0]
        assert "Last Completed Session" in row
        assert "Child Name" in row
        assert "Parent Name" in row
        assert "Therapist Name" in row
        assert "Reason" not in row


def test_parent_portal_usage_json():
    r = client.get(
        "/api/v1/admin/hr-reports/parent-portal-usage",
        headers=_auth_headers("superadmin@demo.com"),
    )
    assert r.status_code == 200
    data = r.json()
    assert "rows" in data
    assert data["count"] == len(data["rows"])
    if data["rows"]:
        row = data["rows"][0]
        assert "Case ID" in row
        assert "Child Name" in row
        assert "Parent Name" in row
        assert "Therapist Name" in row
        assert "Therapist ID" in row
        assert "Login Status" in row
        assert "Last Login" in row
        assert "Days Since Last Activity" in row
        assert "Has Logged In" not in row
        assert "Last Seen" not in row
        assert "Client Name" not in row


def test_parent_portal_usage_csv():
    r = client.get(
        "/api/v1/admin/hr-reports/parent-portal-usage?format=csv",
        headers=_auth_headers("superadmin@demo.com"),
    )
    assert r.status_code == 200
    assert "text/csv" in r.headers.get("content-type", "")
    header = r.text.splitlines()[0]
    assert "Parent Name" in header
    assert "Child Name" in header
    assert "Therapist Name" in header
    assert "Login Status" in header
    assert "Last Login" in header
    assert "Has Logged In" not in header
    assert "Last Seen" not in header


def test_incident_reports_json():
    r = client.get(
        "/api/v1/admin/hr-reports/incident-reports",
        headers=_auth_headers("superadmin@demo.com"),
    )
    assert r.status_code == 200
    data = r.json()
    assert "rows" in data
    assert data["count"] == len(data["rows"])
    if data["rows"]:
        row = data["rows"][0]
        assert "Incident ID" in row
        assert "Case ID" in row
        assert "Child Name" in row
        assert "Parent Name" in row
        assert "Therapist Name" in row
        assert "Category" in row
        assert "Status" in row
        assert "Description" in row


def test_incident_reports_csv():
    r = client.get(
        "/api/v1/admin/hr-reports/incident-reports?format=csv",
        headers=_auth_headers("hr@demo.com"),
    )
    assert r.status_code == 200
    assert "text/csv" in r.headers.get("content-type", "")
    header = r.text.splitlines()[0]
    assert "Incident ID" in header
    assert "Reporter Role" in header


def test_cm_meetings_pdf():
    r = client.get(
        "/api/v1/admin/hr-reports/cm-meetings?format=pdf&month=2026-01",
        headers=_auth_headers("superadmin@demo.com"),
    )
    assert r.status_code == 200
    assert r.headers.get("content-type") == "application/pdf"
    assert r.content[:4] == b"%PDF"


def test_therapist_log_compliance_catalog_and_json():
    r = client.get("/api/v1/admin/hr-reports/catalog", headers=_auth_headers("superadmin@demo.com"))
    assert r.status_code == 200
    keys = {item["key"] for item in r.json()["reports"]}
    assert "therapist-log-compliance" in keys

    r = client.get(
        "/api/v1/admin/hr-reports/therapist-log-compliance",
        headers=_auth_headers("superadmin@demo.com"),
    )
    assert r.status_code == 200
    data = r.json()
    assert "rows" in data
    if data["rows"]:
        row = data["rows"][0]
        assert "Therapist ID" in row
        assert "Therapist Name" in row
        assert "Case ID" in row
        assert "Child Name" in row
        assert "Parent Name" in row
        assert "Client Name" not in row
        assert "Not Submitting Since" in row
        assert "Missing Logs" in row
        assert "Case IDs" not in row
        assert "Active Cases" not in row


def test_therapist_log_compliance_xlsx():
    r = client.get(
        "/api/v1/admin/hr-reports/therapist-log-compliance?format=xlsx",
        headers=_auth_headers("superadmin@demo.com"),
    )
    assert r.status_code == 200
    assert r.headers.get("content-type", "").startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
