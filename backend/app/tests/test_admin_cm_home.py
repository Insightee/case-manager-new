"""Case Manager dedicated home API."""

from fastapi.testclient import TestClient

from app.main import app
from app.seed.demo_seed import run as seed_run
from app.services.admin_cm_home_service import _caseload_target_tab

client = TestClient(app)


def setup_module():
    seed_run()


def _login(email: str) -> dict[str, str]:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "demo123"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_cm_home_for_case_manager():
    r = client.get("/api/v1/admin/cm/home", headers=_login("casemanager@demo.com"))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["role"] == "CASE_MANAGER"
    assert body["landing_route"] == "/admin/cm"
    assert "caseload_summary" in body
    assert "caseload" in body
    assert "sections" in body
    assert isinstance(body["quick_actions"], list)


def test_cm_home_forbidden_for_finance():
    r = client.get("/api/v1/admin/cm/home", headers=_login("finance@demo.com"))
    assert r.status_code == 403


def test_cm_home_for_super_admin():
    r = client.get("/api/v1/admin/cm/home", headers=_login("superadmin@demo.com"))
    assert r.status_code == 200


def test_caseload_target_tab_mapping():
    assert _caseload_target_tab("reports_logs", reports_under_review=2, missing_logs=0) == "reports"
    assert _caseload_target_tab("reports_logs", reports_under_review=0, missing_logs=3) == "logs"
    assert _caseload_target_tab("iep", reports_under_review=0, missing_logs=0) == "iep"
    assert _caseload_target_tab("pending_allotment", reports_under_review=0, missing_logs=0) == "assignments"
    assert _caseload_target_tab("compliance", reports_under_review=0, missing_logs=1) == "logs"
    assert _caseload_target_tab("compliance", reports_under_review=0, missing_logs=0) == "activity"


def test_cm_home_caseload_href_includes_tab():
    r = client.get("/api/v1/admin/cm/home", headers=_login("casemanager@demo.com"))
    assert r.status_code == 200
    rows = r.json().get("caseload") or []
    for row in rows:
        href = row.get("href") or ""
        assert "?tab=" in href, href


def test_cm_log_review_queue_for_case_manager():
    r = client.get("/api/v1/admin/cm/logs/review-queue", headers=_login("casemanager@demo.com"))
    assert r.status_code == 200, r.text
    body = r.json()
    assert "total_pending" in body
    assert "cases" in body
    assert isinstance(body["cases"], list)
    for case_row in body["cases"]:
        assert case_row["pending_count"] == len(case_row.get("logs") or [])
        for log_row in case_row.get("logs") or []:
            assert log_row.get("approval_status") == "PENDING"
            assert "session" in log_row


def test_cm_home_log_items_link_to_review_ui():
    r = client.get("/api/v1/admin/cm/home", headers=_login("casemanager@demo.com"))
    assert r.status_code == 200
    logs = (r.json().get("sections") or {}).get("logs") or {}
    for item in logs.get("items") or []:
        href = item.get("href") or ""
        if href:
            assert href.startswith("/admin/cm/logs"), href
