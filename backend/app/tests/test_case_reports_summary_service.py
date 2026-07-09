"""Case reports summary — due rules and attention ordering."""

from __future__ import annotations

from datetime import date, timedelta

from fastapi.testclient import TestClient

from app.core.database import SessionLocal, ensure_sqlite_schema_patches
from app.main import app
from app.models.case import Case
from app.services import case_reports_summary_service as crs

ensure_sqlite_schema_patches()
client = TestClient(app)


def _login(email: str, password: str = "demo123") -> dict:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_monthly_due_date_uses_28th():
    assert crs.monthly_due_date(2026, 7) == date(2026, 7, 28)
    assert crs.monthly_due_date(2026, 2) == date(2026, 2, 28)


def test_attention_priority_ordering():
    items = [
        {"priority": "pending_cm_approval"},
        {"priority": "overdue"},
        {"priority": "due_soon"},
        {"priority": "needs_changes"},
    ]
    items.sort(key=lambda x: crs.ATTENTION_PRIORITY.get(x["priority"], 99))
    assert [x["priority"] for x in items] == [
        "overdue",
        "needs_changes",
        "due_soon",
        "pending_cm_approval",
    ]


def test_due_soon_within_seven_days():
    soon = crs._due_soon_flag(date.today() + timedelta(days=3))
    assert soon == "due_soon"
    past = crs._due_soon_flag(date.today() - timedelta(days=1))
    assert past == "overdue"


def test_case_reports_summary_endpoint_for_therapist():
    headers = _login("therapist@demo.com")
    with SessionLocal() as db:
        case = db.query(Case).first()
        assert case is not None
        case_id = case.id
    r = client.get(f"/api/v1/cases/{case_id}/reports/summary", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["case_id"] == case_id
    assert "attention_items" in body
    assert "current_status" in body
    assert len(body["current_status"]) == 5
    assert "history" in body
    assert "create_actions" in body
    types = {c["type"] for c in body["create_actions"]}
    assert "observation_report" in types
    assert "monthly_report" in types


def test_build_summary_returns_client_block():
    headers = _login("therapist@demo.com")
    with SessionLocal() as db:
        case = db.query(Case).first()
        case_id = case.id
    r = client.get(f"/api/v1/cases/{case_id}/reports/summary", headers=headers)
    client_block = r.json()["client"]
    assert "name" in client_block
    assert "service_type" in client_block
