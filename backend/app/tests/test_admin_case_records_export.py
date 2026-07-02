"""Tests for admin case records CSV export."""
from __future__ import annotations

import csv
import io

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.database import get_db
from app.main import app
from app.models.case import Case, CaseStatus
from app.models.user import User
from app.services import admin_case_records_export_service as export_svc


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


def test_build_case_records_rows_includes_required_fields(client: TestClient):
    db = next(get_db())
    try:
        case = db.scalars(select(Case).where(Case.status == CaseStatus.ACTIVE).limit(1)).first()
        assert case is not None
        user = db.scalars(select(User).where(User.email == "superadmin@demo.com")).first()
        rows = export_svc.build_case_records_rows(db, user)
        match = [r for r in rows if r["case_code"] == case.case_code]
        assert match, "Expected seeded case in export rows"
        row = match[0]
        assert "external_client_id" in row
        assert "therapist_external_id" in row
        assert "case_create_date" in row
        assert "session_log_count" in row
        assert "session_logs_due" in row
        assert "approval_pending" in row
        assert "leaves_taken" in row
        assert "approved_child_absence" in row
    finally:
        db.close()


def test_cases_records_export_csv_endpoint(client: TestClient):
    token = _login()
    res = client.get("/api/v1/admin/cases/export/records.csv", headers=_auth(token))
    assert res.status_code == 200, res.text
    assert "text/csv" in res.headers.get("content-type", "")
    assert "attachment" in res.headers.get("content-disposition", "").lower()

    reader = csv.DictReader(io.StringIO(res.text))
    headers = reader.fieldnames or []
    assert "Case Id" in headers
    assert "Client id" in headers
    assert "Approval pending" in headers
    assert "Approved child absence" in headers
    rows = list(reader)
    assert len(rows) >= 1
