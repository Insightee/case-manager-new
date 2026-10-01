from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.seed.demo_seed import run as seed_run

client = TestClient(app)


def setup_module():
    seed_run()


def _headers(email: str) -> dict:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "demo123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_dashboard_summary_includes_all_statuses_and_leadership():
    headers = _headers("superadmin@demo.com")
    r = client.get("/api/v1/admin/dashboard/summary?period_month=2026-10", headers=headers)
    assert r.status_code == 200
    data = r.json()
    breakdown = data["status_breakdown"]
    for key in (
        "ACTIVE",
        "PENDING_ALLOTMENT",
        "SUSPENDED",
        "PENDING_REPLACEMENT",
        "DEACTIVATED",
        "CLOSED",
    ):
        assert key in breakdown
        assert isinstance(breakdown[key], int)
    assert "in_progress_tickets" in data
    assert data["tickets_needing_action"] == data["open_tickets"] + data["in_progress_tickets"]
    leadership = data["leadership"]
    assert leadership["period"]["timezone"] == "Asia/Kolkata"
    assert leadership["period"]["month"] == "2026-10"
    modules = leadership["modules"]
    for name in (
        "cases",
        "assignments",
        "sessions",
        "finance",
        "tickets",
        "staffAttendance",
        "queues",
        "therapistAttention",
        "dataExceptions",
    ):
        assert name in modules
        assert "ok" in modules[name]
    queues = modules["queues"]
    if queues.get("ok") and not queues.get("unavailable"):
        keys = [item["key"] for item in queues.get("items") or []]
        assert len(keys) == len(set(keys))
    attendance = modules["staffAttendance"]
    if attendance.get("ok") and not attendance.get("unavailable"):
        assert attendance.get("source") == "in_app_staff_attendance"
        assert "HRIS" not in (attendance.get("coverageNote") or "")
    finance = modules["finance"]
    if finance.get("ok") and not finance.get("unavailable"):
        assert "recognised" not in str(finance).lower()
        assert finance.get("outstandingDateBasis") == "current"


def test_therapist_attention_and_exceptions_permissions():
    admin = _headers("superadmin@demo.com")
    attn = client.get("/api/v1/admin/leadership/therapist-attention", headers=admin)
    assert attn.status_code == 200
    body = attn.json()
    assert "rows" in body
    assert body.get("previewLimited") is False or body["count"] > len(body["rows"])
    assert "No recorded login" in (body.get("loginNote") or "")

    exc = client.get("/api/v1/admin/leadership/data-exceptions", headers=admin)
    assert exc.status_code == 200
    assert "rows" in exc.json()

    parent = client.post("/api/v1/auth/login", json={"email": "parent@demo.com", "password": "demo123"})
    parent_headers = {"Authorization": f"Bearer {parent.json()['access_token']}"}
    denied = client.get("/api/v1/admin/leadership/therapist-attention", headers=parent_headers)
    assert denied.status_code in (401, 403)


def test_ticket_report_still_on_support_hub():
    headers = _headers("superadmin@demo.com")
    r = client.get("/api/v1/admin/support/ticket-report", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert data.get("filters", {}).get("timezone") == "Asia/Kolkata"
    assert "queue_truncated" in data
    assert "queue_total" in data
