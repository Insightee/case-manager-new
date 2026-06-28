"""Observation landing summary + start endpoints."""
from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.database import SessionLocal, ensure_sqlite_schema_patches
from app.main import app
from app.models.case import Case

client = TestClient(app)
ensure_sqlite_schema_patches()


def _login(email: str, password: str = "demo123") -> str:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def test_observation_summary_and_start():
    token = _login("therapist@demo.com")
    headers = {"Authorization": f"Bearer {token}"}

    with SessionLocal() as db:
        case = db.scalars(select(Case).where(Case.case_code == "IC-2026-041")).first()
        assert case is not None
        case_id = case.id

    r = client.get(f"/api/v1/cases/{case_id}/reports/observation/summary", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "has_report" in data
    assert "status_label" in data

    r = client.post(f"/api/v1/cases/{case_id}/reports/observation/start", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json().get("report_id")

    r = client.get(f"/api/v1/cases/{case_id}/reports/observation/summary", headers=headers)
    assert r.status_code == 200
    assert r.json()["has_report"] is True
