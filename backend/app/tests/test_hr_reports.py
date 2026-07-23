from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.seed.demo_seed import run as seed_run

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
        assert "Therapist ID" in data["rows"][0]


def test_session_log_detail_csv():
    r = client.get(
        "/api/v1/admin/hr-reports/session-log-detail?format=csv&date_from=2026-01-01&date_to=2026-12-31",
        headers=_auth_headers("superadmin@demo.com"),
    )
    assert r.status_code == 200
    assert "text/csv" in r.headers.get("content-type", "")
    assert "Case ID" in r.text.splitlines()[0]


def test_inactive_clients_xlsx():
    r = client.get(
        "/api/v1/admin/hr-reports/inactive-clients?format=xlsx",
        headers=_auth_headers("superadmin@demo.com"),
    )
    assert r.status_code == 200
    assert r.headers.get("content-type", "").startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


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
        assert "Login Status" in row
        assert "Has Logged In" in row
        assert "Days Since Last Activity" in row


def test_parent_portal_usage_csv():
    r = client.get(
        "/api/v1/admin/hr-reports/parent-portal-usage?format=csv",
        headers=_auth_headers("superadmin@demo.com"),
    )
    assert r.status_code == 200
    assert "text/csv" in r.headers.get("content-type", "")
    header = r.text.splitlines()[0]
    assert "Parent Name" in header
    assert "Last Seen" in header


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
        assert "Not Submitting Since" in row
        assert "Missing Logs" in row


def test_therapist_log_compliance_xlsx():
    r = client.get(
        "/api/v1/admin/hr-reports/therapist-log-compliance?format=xlsx",
        headers=_auth_headers("superadmin@demo.com"),
    )
    assert r.status_code == 200
    assert r.headers.get("content-type", "").startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
