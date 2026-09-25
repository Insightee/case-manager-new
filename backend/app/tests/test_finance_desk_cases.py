"""Finance desk: view-only cases, redacted logs, approved leave only."""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.timezone import today_ist
from app.main import app
from app.models.assignment import CaseAssignment, CaseAssignmentStatus
from app.models.daily_log import DailyLog, LogApprovalStatus
from app.models.leave import LeaveBillingCategory, LeaveStatus, LeaveType, TherapistLeave
from app.models.session import Session as TherapySession
from app.models.session import SessionStatus
from app.models.session_absence import SessionAbsenceRequest, SessionAbsenceStatus, SessionAbsenceType
from app.models.user import User
from app.seed.demo_seed import run as seed_run
from app.tests.conftest import api_first_case_id, api_items, login_headers

client = TestClient(app)

CLINICAL_KEYS = {
    "session_notes",
    "observations",
    "activities_done",
    "goals_addressed",
    "parent_notes",
    "follow_ups",
}


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    seed_run()


def _finance_headers() -> dict:
    return login_headers(client, "finance@demo.com")


def _insert_leave_and_logs() -> tuple[int, int, int]:
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
        pending = TherapistLeave(
            therapist_user_id=therapist.id,
            leave_type=LeaveType.CASUAL,
            billing_category=LeaveBillingCategory.UNPAID,
            start_date=date(2026, 9, 1),
            end_date=date(2026, 9, 1),
            reason="Finance desk pending should be hidden",
            status=LeaveStatus.PENDING,
        )
        approved = TherapistLeave(
            therapist_user_id=therapist.id,
            leave_type=LeaveType.ANNUAL,
            billing_category=LeaveBillingCategory.PAID,
            start_date=date(2026, 9, 2),
            end_date=date(2026, 9, 2),
            reason="Finance desk approved leave",
            status=LeaveStatus.APPROVED,
        )
        db.add_all([pending, approved])
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
            activities_done="Should not reach finance.",
            parent_notes="Should not reach finance.",
            session_notes="FINANCE_CLINICAL_SECRET",
            observations="Hidden observation.",
            approval_status=LogApprovalStatus.PENDING.value,
            submitted_at=now,
        )
        db.add(log)
        pending_absence = SessionAbsenceRequest(
            session_id=session.id,
            case_id=assignment.case_id,
            therapist_user_id=therapist.id,
            absence_type=SessionAbsenceType.CLIENT_ABSENT,
            status=SessionAbsenceStatus.PENDING_APPROVAL,
            reason="Pending child absence hidden from finance",
            requested_by_user_id=therapist.id,
        )
        approved_absence = SessionAbsenceRequest(
            session_id=session.id,
            case_id=assignment.case_id,
            therapist_user_id=therapist.id,
            absence_type=SessionAbsenceType.CLIENT_ABSENT,
            status=SessionAbsenceStatus.APPROVED,
            reason="Approved child absence for finance",
            requested_by_user_id=therapist.id,
        )
        db.add_all([pending_absence, approved_absence])
        db.commit()
        return pending.id, log.id, assignment.case_id
    finally:
        db.close()


def test_finance_pipeline_returns_cases():
    headers = _finance_headers()
    board = client.get("/api/v1/admin/cases/pipeline", headers=headers)
    assert board.status_code == 200, board.text
    body = board.json()
    assert body.get("total_cases", 0) > 0
    case_id = api_first_case_id(client, headers)
    detail = client.get(f"/api/v1/cases/{case_id}", headers=headers)
    assert detail.status_code == 200, detail.text
    billing = client.patch(
        f"/api/v1/cases/{case_id}/billing",
        headers=headers,
        json={"client_rate_per_session_inr": 1},
    )
    assert billing.status_code == 403


def test_finance_leave_lists_approved_only():
    pending_id, _log_id, _case_id = _insert_leave_and_logs()
    headers = _finance_headers()
    res = client.get("/api/v1/leave", headers=headers)
    assert res.status_code == 200, res.text
    rows = res.json()
    assert isinstance(rows, list)
    assert rows, "Expected at least the approved leave fixture"
    assert all(str(row.get("status") or "").upper() == "APPROVED" for row in rows)
    assert pending_id not in {row.get("id") for row in rows}

    filtered = client.get("/api/v1/leave?leave_status=PENDING", headers=headers)
    assert filtered.status_code == 200, filtered.text
    assert all(str(row.get("status") or "").upper() == "APPROVED" for row in filtered.json())

    patch = client.patch(
        f"/api/v1/leave/{pending_id}",
        headers=headers,
        json={"status": "APPROVED"},
    )
    assert patch.status_code == 403

    report = client.get("/api/v1/leave/period-export?year=2026", headers=headers)
    assert report.status_code == 403

    absences = client.get("/api/v1/leave/child-absence", headers=headers)
    assert absences.status_code == 200, absences.text
    items = absences.json().get("items") or []
    assert items
    assert all(str(item.get("leave_status") or item.get("status") or "").upper() == "APPROVED" for item in items)

    pending_queue = client.get("/api/v1/sessions/absence/pending", headers=headers)
    assert pending_queue.status_code == 403


def test_finance_daily_logs_are_attendance_only():
    _pending_id, log_id, case_id = _insert_leave_and_logs()
    headers = _finance_headers()
    listed = client.get(f"/api/v1/daily-logs?case_id={case_id}", headers=headers)
    assert listed.status_code == 200, listed.text
    payload = listed.json()
    rows = api_items(payload) if isinstance(payload, dict) else payload
    match = next((row for row in rows if row.get("id") == log_id), None)
    assert match is not None
    assert match.get("approval_status") in ("PENDING", LogApprovalStatus.PENDING.value)
    for key in CLINICAL_KEYS:
        assert key not in match
    assert "FINANCE_CLINICAL_SECRET" not in str(match)

    detail = client.get(f"/api/v1/daily-logs/{log_id}", headers=headers)
    assert detail.status_code == 200, detail.text
    body = detail.json()
    for key in CLINICAL_KEYS:
        assert key not in body
    assert body.get("session_notes") is None
    assert "FINANCE_CLINICAL_SECRET" not in str(body)

    pdf = client.get(f"/api/v1/daily-logs/{log_id}/download", headers=headers)
    assert pdf.status_code == 403

    approve = client.post(f"/api/v1/daily-logs/{log_id}/approve", headers=headers)
    assert approve.status_code == 403
