from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.seed.demo_seed import run as seed_run

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    seed_run()


def _login(email: str) -> str:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "demo123"})
    assert r.status_code == 200
    return r.json()["access_token"]


def test_superadmin_dashboard_and_cases():
    token = _login("superadmin@demo.com")
    headers = {"Authorization": f"Bearer {token}"}
    dash = client.get("/api/v1/admin/dashboard/summary", headers=headers)
    assert dash.status_code == 200
    assert "open_cases" in dash.json()
    cases = client.get("/api/v1/cases", headers=headers)
    assert cases.status_code == 200
    assert len(cases.json()) >= 2


def test_case_manager_can_review_report():
    token = _login("casemanager@demo.com")
    headers = {"Authorization": f"Bearer {token}"}
    reports = client.get("/api/v1/reports/monthly", headers=headers)
    assert reports.status_code == 200
    under_review = [r for r in reports.json() if r["status"] == "UNDER_REVIEW"]
    if under_review:
        rid = under_review[0]["id"]
        res = client.post(
            f"/api/v1/reports/monthly/{rid}/approve",
            headers=headers,
            json={"comment": "Approved in test", "visibility_status": "APPROVED_FOR_PARENT"},
        )
        assert res.status_code == 200


def test_parent_only_sees_approved_reports():
    token = _login("parent@demo.com")
    headers = {"Authorization": f"Bearer {token}"}
    reports = client.get("/api/v1/parent/reports", headers=headers)
    assert reports.status_code == 200
    for r in reports.json():
        assert r["status"] == "approved"


def test_daily_log_requires_session():
    token = _login("therapist@demo.com")
    headers = {"Authorization": f"Bearer {token}"}
    bad = client.post(
        "/api/v1/daily-logs",
        headers=headers,
        json={"session_id": 99999, "attendance_status": "PRESENT"},
    )
    assert bad.status_code in (400, 404)


def test_supervisor_dashboard():
    token = _login("supervisor@demo.com")
    headers = {"Authorization": f"Bearer {token}"}
    dash = client.get("/api/v1/admin/dashboard/summary", headers=headers)
    assert dash.status_code == 200


def test_finance_cannot_manage_users():
    token = _login("finance@demo.com")
    headers = {"Authorization": f"Bearer {token}"}
    users = client.get("/api/v1/admin/users", headers=headers)
    assert users.status_code == 403


def test_module_catalog_and_scoped_admin():
    token = _login("superadmin@demo.com")
    headers = {"Authorization": f"Bearer {token}"}
    catalog = client.get("/api/v1/admin/modules", headers=headers)
    assert catalog.status_code == 200
    assert "homecare" in catalog.json()["role_defaults"]["ADMIN"]

    scoped = _login("admin@demo.com")
    scoped_headers = {"Authorization": f"Bearer {scoped}"}
    me = client.get("/api/v1/auth/me", headers=scoped_headers)
    assert me.status_code == 200
    body = me.json()
    assert "homecare" in body["module_assignments"]
    assert "cases" in body["features"]
    assert "invoices" not in body["features"]

    cases = client.get("/api/v1/cases", headers=scoped_headers)
    assert cases.status_code == 200
    modules = {c["product_module"] for c in cases.json()}
    assert modules <= {"homecare"}


def test_create_user_requires_modules_for_admin():
    import uuid

    email = f"scoped-{uuid.uuid4().hex[:8]}@demo.com"
    token = _login("superadmin@demo.com")
    headers = {"Authorization": f"Bearer {token}"}
    bad = client.post(
        "/api/v1/admin/users",
        headers=headers,
        json={
            "email": email,
            "password": "demo123",
            "full_name": "Scoped Only",
            "role_names": ["ADMIN"],
            "module_assignments": [],
        },
    )
    assert bad.status_code == 400

    ok = client.post(
        "/api/v1/admin/users",
        headers=headers,
        json={
            "email": email,
            "password": "demo123",
            "full_name": "Scoped Only",
            "role_names": ["ADMIN"],
            "module_assignments": ["shadow_support"],
        },
    )
    assert ok.status_code == 201
    assert ok.json()["module_assignments"] == ["shadow_support"]


def test_approve_log_makes_parent_visible():
    seed_run()
    admin_token = _login("casemanager@demo.com")
    parent_token = _login("parent@demo.com")
    headers = {"Authorization": f"Bearer {admin_token}"}
    logs = client.get("/api/v1/daily-logs?approval_status=PENDING", headers=headers)
    assert logs.status_code == 200
    pending = [l for l in logs.json() if l.get("parent_notes")]
    if not pending:
        return
    log_id = pending[0]["id"]
    res = client.post(f"/api/v1/daily-logs/{log_id}/approve", headers=headers)
    assert res.status_code == 200
    parent_headers = {"Authorization": f"Bearer {parent_token}"}
    parent_logs = client.get("/api/v1/parent/session-logs", headers=parent_headers)
    assert parent_logs.status_code == 200
    assert any(pl["id"] == log_id for pl in parent_logs.json())


def test_scoped_admin_dashboard_invoices_module():
    token = _login("admin@demo.com")
    headers = {"Authorization": f"Bearer {token}"}
    dash = client.get("/api/v1/admin/dashboard/summary", headers=headers)
    assert dash.status_code == 200
    assert dash.json()["invoices_pending"] == 0


def test_incident_patch():
    token = _login("supervisor@demo.com")
    headers = {"Authorization": f"Bearer {token}"}
    incidents = client.get("/api/v1/incidents", headers=headers)
    assert incidents.status_code == 200
    if not incidents.json():
        return
    iid = incidents.json()[0]["id"]
    res = client.patch(
        f"/api/v1/incidents/{iid}",
        headers=headers,
        json={"status": "RESOLVED"},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "RESOLVED"


def test_attachment_share_with_parent():
    token = _login("casemanager@demo.com")
    headers = {"Authorization": f"Bearer {token}"}
    cases = client.get("/api/v1/cases", headers=headers)
    case_id = cases.json()[0]["id"]
    attachments = client.get(f"/api/v1/attachments?case_id={case_id}", headers=headers)
    if attachments.status_code != 200 or not attachments.json():
        return
    aid = attachments.json()[0]["id"]
    res = client.patch(
        f"/api/v1/attachments/{aid}",
        headers=headers,
        json={"visibility_status": "APPROVED_FOR_PARENT"},
    )
    assert res.status_code == 200
    assert res.json()["visibility_status"] == "APPROVED_FOR_PARENT"


def test_report_detail_endpoint():
    token = _login("superadmin@demo.com")
    headers = {"Authorization": f"Bearer {token}"}
    reports = client.get("/api/v1/reports/monthly", headers=headers)
    assert reports.status_code == 200
    assert reports.json()
    rid = reports.json()[0]["id"]
    detail = client.get(f"/api/v1/reports/monthly/{rid}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["id"] == rid
