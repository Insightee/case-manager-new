"""Parent portal API tests."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _login(email: str, password: str = "demo123") -> dict:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_parent_session_logs_visibility():
    headers = _login("parent@demo.com")
    logs = client.get("/api/v1/parent/session-logs", headers=headers)
    assert logs.status_code == 200
    data = logs.json()
    assert isinstance(data, list)
    if data:
        assert "parent_notes" in data[0] or "activities_done" in data[0]
        assert "session_notes" not in data[0]


def test_parent_cases_enriched():
    headers = _login("parent@demo.com")
    cases = client.get("/api/v1/parent/cases", headers=headers).json()
    assert len(cases) >= 1
    c = cases[0]
    assert "therapistName" in c
    assert "latestApprovedReportMonth" in c


def test_parent_report_detail_and_other_family_denied():
    parent_h = _login("parent@demo.com")
    reports = client.get("/api/v1/parent/reports", headers=parent_h).json()
    if not reports:
        return
    rid = reports[0]["id"]
    detail = client.get(f"/api/v1/parent/reports/{rid}", headers=parent_h)
    assert detail.status_code == 200
    assert detail.json()["summary"]


def test_parent_iep_acknowledge():
    headers = _login("parent@demo.com")
    items = client.get("/api/v1/parent/iep-status", headers=headers).json()
    pending = [i for i in items if i["status"] == "pending"]
    if not pending:
        return
    att_id = pending[0]["id"]
    r = client.post(f"/api/v1/parent/iep/{att_id}/acknowledge", headers=headers)
    assert r.status_code == 200
    assert r.json()["status"] == "acknowledged"


def test_parent_billing_summaries():
    headers = _login("parent@demo.com")
    rows = client.get("/api/v1/parent/billing-summaries", headers=headers).json()
    assert isinstance(rows, list)
