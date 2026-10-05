"""Clinical report engine status transitions."""
from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.database import SessionLocal, ensure_sqlite_schema_patches
from app.main import app
from app.models.case import Case
from app.models.clinical_report import ClinicalReport, ClinicalReportStatus
from app.report_engine_constants import REQUIRED_OBSERVATION_SECTION_KEYS

client = TestClient(app)
ensure_sqlite_schema_patches()

SAMPLE = "Structured observation notes with enough detail for completion gate."


def _login(email: str, password: str = "demo123") -> str:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _fill_required_sections(report_id: int, headers: dict) -> None:
    for key in REQUIRED_OBSERVATION_SECTION_KEYS:
        r = client.patch(
            f"/api/v1/reports/{report_id}/sections/{key}",
            headers=headers,
            json={"narrative_text": SAMPLE},
        )
        assert r.status_code == 200, r.text


def test_report_engine_submit_approve_lock_flow():
    therapist_token = _login("therapist@demo.com")
    admin_token = _login("superadmin@demo.com")
    headers = {"Authorization": f"Bearer {therapist_token}"}
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    with SessionLocal() as db:
        case = db.scalars(select(Case).where(Case.case_code == "IC-2026-041")).first()
        assert case is not None
        case_id = case.id

    ws = client.get(f"/api/v1/cases/{case_id}/reports/observation", headers=headers)
    assert ws.status_code == 200, ws.text
    report_id = ws.json()["report_id"]
    assert report_id

    _fill_required_sections(report_id, headers)

    r = client.post(f"/api/v1/reports/{report_id}/submit", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == ClinicalReportStatus.SUBMITTED_FOR_REVIEW.value

    denied = client.post(f"/api/v1/reports/{report_id}/approve", headers=headers, json={})
    assert denied.status_code == 403
    assert "reviewer role" in (denied.json().get("detail") or "").lower()

    r = client.post(f"/api/v1/reports/{report_id}/approve", headers=admin_headers, json={"share_with_parent": False})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == ClinicalReportStatus.LOCKED.value

    r = client.patch(
        f"/api/v1/reports/{report_id}/sections/child_snapshot",
        headers=headers,
        json={"narrative_text": "Should not save"},
    )
    assert r.status_code == 403

    r = client.post(f"/api/v1/reports/{report_id}/approve", headers=headers, json={})
    assert r.status_code == 403


def test_report_engine_return_reopens_therapist_edit():
    therapist_token = _login("therapist@demo.com")
    admin_token = _login("superadmin@demo.com")
    headers = {"Authorization": f"Bearer {therapist_token}"}
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    with SessionLocal() as db:
        case = db.scalars(select(Case).where(Case.case_code == "IC-2026-042")).first()
        if not case:
            case = db.scalars(select(Case).where(Case.case_code == "IC-2026-041")).first()
        assert case is not None
        case_id = case.id

    ws = client.get(f"/api/v1/cases/{case_id}/reports/observation", headers=headers)
    assert ws.status_code == 200, ws.text
    if ws.json().get("status") == ClinicalReportStatus.LOCKED.value:
        start = client.post(f"/api/v1/cases/{case_id}/reports/observation/start", headers=headers)
        assert start.status_code == 200, start.text
        report_id = start.json()["report_id"]
    else:
        report_id = ws.json()["report_id"]
    _fill_required_sections(report_id, headers)
    client.post(f"/api/v1/reports/{report_id}/submit", headers=headers)

    r = client.post(
        f"/api/v1/reports/{report_id}/return",
        headers=admin_headers,
        json={"comment": "Please expand regulation section"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == ClinicalReportStatus.RETURNED_FOR_CHANGES.value

    r = client.patch(
        f"/api/v1/reports/{report_id}/sections/regulation_sensory",
        headers=headers,
        json={"narrative_text": SAMPLE},
    )
    assert r.status_code == 200, r.text
