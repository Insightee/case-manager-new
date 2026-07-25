"""Tests for admin therapist profile CSV export."""
from __future__ import annotations

import csv
import io

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.main import app
from app.services import therapist_profile_export_service as export_svc


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


def test_build_export_rows_includes_required_fields(client: TestClient):
    db = next(get_db())
    try:
        rows = export_svc.build_export_rows(db)
        assert rows, "Expected at least one therapist profile in export rows"
        row = rows[0]
        for key in [
            "external_employee_id",
            "full_name",
            "display_name",
            "email",
            "phone",
            "start_date",
            "services",
            "pending_changes",
            "short_bio",
            "qualifications",
            "primary_case_manager",
            "mentor",
            "region",
        ]:
            assert key in row
        assert row["pending_changes"] in {"Yes", "No"}
    finally:
        db.close()


def test_therapist_profiles_export_csv_endpoint(client: TestClient):
    token = _login()
    res = client.get("/api/v1/admin/therapist-profiles/export.csv", headers=_auth(token))
    assert res.status_code == 200, res.text
    assert "text/csv" in res.headers.get("content-type", "")
    assert "attachment" in res.headers.get("content-disposition", "").lower()

    reader = csv.DictReader(io.StringIO(res.text))
    headers = reader.fieldnames or []
    assert "External employee ID" in headers
    assert "Full name" in headers
    assert "Display name" in headers
    assert "Email" in headers
    assert "Phone" in headers
    assert "Start date" in headers
    assert "Services" in headers
    assert "Pending changes" in headers
    assert "Short bio" in headers
    assert "Qualifications" in headers
    assert "Primary case manager" in headers
    assert "Mentor" in headers
    assert "Region" in headers
    rows = list(reader)
    assert len(rows) >= 1


def test_therapist_profiles_export_respects_status_filter(client: TestClient):
    token = _login()
    all_res = client.get("/api/v1/admin/therapist-profiles/export.csv", headers=_auth(token))
    approved_res = client.get(
        "/api/v1/admin/therapist-profiles/export.csv?status=APPROVED",
        headers=_auth(token),
    )
    assert all_res.status_code == 200
    assert approved_res.status_code == 200
    all_rows = list(csv.DictReader(io.StringIO(all_res.text)))
    approved_rows = list(csv.DictReader(io.StringIO(approved_res.text)))
    assert len(approved_rows) <= len(all_rows)
