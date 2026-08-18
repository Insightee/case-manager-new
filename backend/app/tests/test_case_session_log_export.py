from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from io import BytesIO
from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.timezone import today_ist
from app.main import app
from app.models.assignment import CaseAssignment, CaseAssignmentStatus
from app.models.daily_log import DailyLog, LogApprovalStatus
from app.models.session import Session as TherapySession
from app.models.session import SessionStatus
from app.models.user import User
from app.seed.demo_seed import run as seed_run
from app.services import case_session_log_export_service as export_svc

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def _seed():
    seed_run()


def _login(email: str, password: str = "demo123") -> dict:
    res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _seed_case_log_with_notes(*, approve: bool = True) -> tuple[int, int]:
    db = SessionLocal()
    try:
        therapist = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
        assignment = db.scalars(
            select(CaseAssignment).where(
                CaseAssignment.therapist_user_id == therapist.id,
                CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
            )
        ).first()
        if not therapist or not assignment:
            pytest.skip("No active therapist assignment in seed")
        now = datetime.now(timezone.utc)
        session = TherapySession(
            case_id=assignment.case_id,
            therapist_user_id=therapist.id,
            scheduled_date=today_ist(),
            status=SessionStatus.COMPLETED,
            actual_start_at=now,
            actual_end_at=now,
            is_additional_visit=True,
        )
        db.add(session)
        db.flush()
        log = DailyLog(
            session_id=session.id,
            attendance_status="PRESENT",
            activities_done="Turn-taking practice",
            parent_notes="Family-facing update",
            session_notes="INTERNAL_BULK_EXPORT_SECRET",
            observations="INTERNAL_OBSERVATION",
            follow_ups="Next week goals",
            approval_status=LogApprovalStatus.APPROVED.value if approve else LogApprovalStatus.PENDING.value,
            submitted_at=now,
        )
        db.add(log)
        db.commit()
        return assignment.case_id, log.id
    finally:
        db.close()


def _xlsx_text(content: bytes) -> str:
    import openpyxl

    wb = openpyxl.load_workbook(BytesIO(content), read_only=True, data_only=True)
    ws = wb.active
    rows = []
    for row in ws.iter_rows(values_only=True):
        rows.append("\t".join("" if cell is None else str(cell) for cell in row))
    return "\n".join(rows)


def test_staff_case_export_summary_excludes_content_by_default():
    case_id, _log_id = _seed_case_log_with_notes(approve=True)
    headers = _login("superadmin@demo.com")
    res = client.get(
        f"/api/v1/cases/{case_id}/session-logs/export/xlsx?view_mode=all&status=approved",
        headers=headers,
    )
    assert res.status_code == 200, res.text
    assert "spreadsheetml" in res.headers.get("content-type", "")
    text = _xlsx_text(res.content)
    assert "Session logs export" in text
    assert "Approval status" in text
    assert "INTERNAL_BULK_EXPORT_SECRET" not in text
    assert "INTERNAL_OBSERVATION" not in text


def test_staff_case_export_include_content():
    case_id, _log_id = _seed_case_log_with_notes(approve=True)
    headers = _login("therapist@demo.com")
    res = client.get(
        f"/api/v1/cases/{case_id}/session-logs/export/xlsx?view_mode=all&include_content=true",
        headers=headers,
    )
    assert res.status_code == 200, res.text
    text = _xlsx_text(res.content)
    assert "INTERNAL_BULK_EXPORT_SECRET" in text
    assert "INTERNAL_OBSERVATION" in text


def test_parent_case_export_excludes_internal_fields_when_content_included():
    case_id, log_id = _seed_case_log_with_notes(approve=True)
    parent = SessionLocal().scalar(
        select(User).where(User.email == "parent@demo.com")
    )
    if not parent:
        pytest.skip("No parent user in seed")
    headers = _login("parent@demo.com")
    res = client.get(
        f"/api/v1/parent/session-logs/export/xlsx?case_id={case_id}&view_mode=all&include_content=true",
        headers=headers,
    )
    assert res.status_code == 200, res.text
    text = _xlsx_text(res.content)
    assert "Family-facing update" in text
    assert "INTERNAL_BULK_EXPORT_SECRET" not in text
    assert "INTERNAL_OBSERVATION" not in text
    assert "Status" in text


def test_parent_export_requires_case_id():
    headers = _login("parent@demo.com")
    res = client.get("/api/v1/parent/session-logs/export/xlsx", headers=headers)
    assert res.status_code == 422


def test_export_service_parent_status_labels():
    db = SessionLocal()
    try:
        _, log_id = _seed_case_log_with_notes(approve=True)
        log = db.get(DailyLog, log_id)
        assert export_svc._parent_status_label(log) == "Reviewed"
    finally:
        db.close()
