"""Admin clinical dashboard RBAC and shape."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.database import SessionLocal, ensure_sqlite_schema_patches
from app.main import app
from app.models.user import User

ensure_sqlite_schema_patches()
client = TestClient(app)


def _token(email: str, password: str = "demo123") -> str:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def test_admin_clinical_dashboard_ok():
    token = _token("superadmin@demo.com")
    r = client.get("/api/v1/admin/clinical-dashboard", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    data = r.json()
    assert "cases" in data
    assert "total_cases" in data


def test_therapist_clinical_dashboard_forbidden():
    token = _token("therapist@demo.com")
    r = client.get("/api/v1/admin/clinical-dashboard", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403


def test_clinical_quality_dashboard_summary():
    token = _token("superadmin@demo.com")
    r = client.get(
        "/api/v1/admin/clinical-quality-dashboard/summary",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    assert "documentation_breakdown" in r.json()
