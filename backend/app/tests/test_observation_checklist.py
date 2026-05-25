"""Observation checklist and clinical profile workflow."""
from __future__ import annotations

import json

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.clinical_constants import OBSERVATION_CHECKLIST_SECTIONS
from app.core.database import SessionLocal, ensure_sqlite_schema_patches
from app.main import app
from app.models.case import Case
from app.models.clinical import ObservationChecklist, ObservationChecklistStatus

client = TestClient(app)
ensure_sqlite_schema_patches()


def _login(email: str, password: str = "demo123") -> str:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def test_observation_checklist_submit_and_approve():
    token = _login("therapist@demo.com")
    admin_token = _login("superadmin@demo.com")

    with SessionLocal() as db:
        case = db.scalars(select(Case).where(Case.case_code == "IC-2026-041")).first()
        assert case is not None
        case_id = case.id
        existing = db.scalars(
            select(ObservationChecklist).where(ObservationChecklist.case_id == case_id)
        ).first()
        if existing:
            existing.status = ObservationChecklistStatus.DRAFT.value
            existing.submitted_at = None
            existing.reviewer_comment = None
            db.commit()

    headers = {"Authorization": f"Bearer {token}"}
    r = client.get(f"/api/v1/cases/{case_id}/observation-checklist", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert len(data["sections"]) == len(OBSERVATION_CHECKLIST_SECTIONS)

    responses = {s["key"]: f"Sample text for {s['key']}" for s in data["sections"]}
    r = client.put(
        f"/api/v1/cases/{case_id}/observation-checklist",
        headers=headers,
        json={"responses": responses, "sync_clinical_profile": True},
    )
    assert r.status_code == 200

    r = client.post(f"/api/v1/cases/{case_id}/observation-checklist/submit", headers=headers)
    assert r.status_code == 200
    assert r.json()["status"] == "SUBMITTED"

    r = client.get("/api/v1/admin/observation-checklists", headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200
    pending = r.json()
    match = next((p for p in pending if p["case_id"] == case_id), None)
    assert match is not None

    checklist_id = match["id"]
    r = client.post(
        f"/api/v1/admin/observation-checklists/{checklist_id}/approve",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"comment": "Looks good", "share_with_parent": True},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "APPROVED"

    parent_token = _login("parent@demo.com")
    r = client.get(
        f"/api/v1/parent/cases/{case_id}/observation-reports",
        headers={"Authorization": f"Bearer {parent_token}"},
    )
    assert r.status_code == 200
    reports = r.json()
    assert len(reports) >= 1

    report_id = reports[0]["id"]
    r = client.get(
        f"/api/v1/parent/reports/observation/{report_id}/download",
        headers={"Authorization": f"Bearer {parent_token}"},
    )
    assert r.status_code == 200
    assert r.headers.get("content-type", "").startswith("application/pdf")
