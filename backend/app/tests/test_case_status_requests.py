"""Therapist case status change requests."""
from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.database import SessionLocal, ensure_sqlite_schema_patches
from app.main import app
from app.models.case import Case
from app.models.case_status_request import CaseStatusRequest, CaseStatusRequestStatus

client = TestClient(app)
ensure_sqlite_schema_patches()


def _login(email: str, password: str = "demo123") -> str:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def test_therapist_status_request_and_admin_approve():
    therapist_token = _login("therapist@demo.com")
    admin_token = _login("superadmin@demo.com")

    with SessionLocal() as db:
        case = db.scalars(select(Case).where(Case.status == "ACTIVE").limit(1)).first()
        assert case is not None
        case_id = case.id
        for row in db.scalars(
            select(CaseStatusRequest).where(
                CaseStatusRequest.case_id == case_id,
                CaseStatusRequest.status == CaseStatusRequestStatus.PENDING,
            )
        ).all():
            row.status = CaseStatusRequestStatus.REJECTED
        db.commit()

    th = {"Authorization": f"Bearer {therapist_token}"}
    r = client.post(
        f"/api/v1/cases/{case_id}/status-requests",
        headers=th,
        json={"to_status": "SUSPENDED", "reason": "Family travel break for two weeks"},
    )
    assert r.status_code == 201, r.text

    r = client.get(f"/api/v1/cases/{case_id}/status-requests", headers=th)
    assert r.status_code == 200
    assert r.json()["pending"]["toStatus"] == "SUSPENDED"

    r = client.get("/api/v1/admin/status-requests", headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200
    pending = [x for x in r.json() if x["caseDbId"] == case_id]
    assert pending
    req_id = pending[0]["id"]

    r = client.post(
        f"/api/v1/admin/status-requests/{req_id}/approve",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"note": "Approved pause"},
    )
    assert r.status_code == 200

    with SessionLocal() as db:
        case = db.get(Case, case_id)
        assert case.status.value == "SUSPENDED"
