"""Leave cancel reinstate + unresolved attendance disposition gates."""

from __future__ import annotations

import os
from datetime import date, time, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import settings
from app.core.database import SessionLocal, engine
from app.core.timezone import today_ist
from app.main import app
from app.models.assignment import CaseAssignment, CaseAssignmentStatus
from app.models.case import Case
from app.models.leave import LeaveStatus, TherapistLeave
from app.models.session import Session as TherapySession
from app.models.session import SessionMode, SessionStatus
from app.models.slot import SlotStatus, TherapistSlot
from app.models.user import User
from app.seed.demo_seed import run as seed_run
from app.services import attendance_resolution_service as attendance_resolution
from app.services import invoice_billing_service as billing
from app.services import leave_notification_service as leave_notify
from app.services import leave_service

client = TestClient(app)


def _reset_sqlite_db() -> None:
    url = settings.database_url
    if not url.startswith("sqlite"):
        return
    rel = url.replace("sqlite:///", "")
    db_path = Path(rel) if os.path.isabs(rel) else Path(__file__).resolve().parents[2] / rel.lstrip("./")
    engine.dispose()
    if db_path.exists():
        db_path.unlink()


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    _reset_sqlite_db()
    seed_run()


def _login(email: str) -> str:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "demo123"})
    assert r.status_code == 200
    return r.json()["access_token"]


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _future_weekday(offset_days: int = 21) -> date:
    d = today_ist() + timedelta(days=offset_days)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


def _clear_unresolved_sessions(therapist_email: str = "therapist@demo.com") -> None:
    """Test helper: drop past SCHEDULED/CANCELLED sessions that block new leave."""
    db = SessionLocal()
    try:
        therapist = db.scalars(select(User).where(User.email == therapist_email)).first()
        assert therapist is not None
        rows = attendance_resolution.list_unresolved_attendance_days(
            db, therapist_user_id=therapist.id
        )
        for row in rows:
            sid = row.get("session_id")
            if not sid:
                continue
            sess = db.get(TherapySession, sid)
            if sess is not None:
                db.delete(sess)
        db.commit()
    finally:
        db.close()


def test_leave_cancel_after_approve_reinstates_sessions():
    _clear_unresolved_sessions()
    therapist = _login("therapist@demo.com")
    hr = _login("hr@demo.com")
    th = _headers(therapist)
    day = _future_weekday(28)

    client.post(
        "/api/v1/slots/materialize",
        headers=th,
        json={"from_date": day.isoformat(), "to_date": day.isoformat()},
    )
    cases = client.get("/api/v1/slots/bookable-cases", headers=th).json()
    case_id = cases[0]["case_id"]
    cal = client.get(
        f"/api/v1/slots/calendar?from_date={day.isoformat()}&to_date={day.isoformat()}",
        headers=th,
    )
    available = [s for s in cal.json()["slots"] if s["status"] == "AVAILABLE"]
    assert available
    slot_id = available[0]["id"]
    assert (
        client.post(
            f"/api/v1/slots/{slot_id}/book",
            headers=th,
            json={"case_id": case_id},
        ).status_code
        == 200
    )

    leave = client.post(
        "/api/v1/leave",
        headers=th,
        json={
            "service_line": "shadow_support",
            "leave_type": "CASUAL",
            "start_date": day.isoformat(),
            "end_date": day.isoformat(),
            "case_ids": [case_id],
        },
    )
    assert leave.status_code == 201, leave.text
    leave_id = leave.json()["id"]

    assert (
        client.patch(
            f"/api/v1/leave/{leave_id}",
            headers=_headers(hr),
            json={"status": "APPROVED"},
        ).status_code
        == 200
    )

    db = SessionLocal()
    try:
        sessions = db.scalars(
            select(TherapySession).where(
                TherapySession.case_id == case_id,
                TherapySession.scheduled_date == day,
            )
        ).all()
        cancelled = [s for s in sessions if s.status == SessionStatus.CANCELLED]
        assert cancelled, "Approve leave should cancel the booked session"
        assert all(
            (s.cancellation_reason or "") == leave_notify.leave_cancel_reason(leave_id)
            for s in cancelled
        )
    finally:
        db.close()

    assert (
        client.patch(
            f"/api/v1/leave/{leave_id}",
            headers=_headers(hr),
            json={"status": "CANCELLED"},
        ).status_code
        == 200
    )

    db = SessionLocal()
    try:
        sessions = db.scalars(
            select(TherapySession).where(
                TherapySession.case_id == case_id,
                TherapySession.scheduled_date == day,
            )
        ).all()
        assert any(s.status == SessionStatus.SCHEDULED for s in sessions)
        assert not any(
            s.status == SessionStatus.CANCELLED
            and (s.cancellation_reason or "") == leave_notify.leave_cancel_reason(leave_id)
            for s in sessions
        )
        slot = db.get(TherapistSlot, slot_id)
        assert slot is not None
        assert slot.status == SlotStatus.BOOKED
        assert slot.case_id == case_id
    finally:
        db.close()


def test_unexplained_cancelled_session_surfaces_on_preview():
    db = SessionLocal()
    try:
        therapist = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
        assignment = db.scalars(
            select(CaseAssignment).where(
                CaseAssignment.therapist_user_id == therapist.id,
                CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
            )
        ).first()
        case = db.get(Case, assignment.case_id)
        day = today_ist() - timedelta(days=3)
        while day.weekday() >= 5:
            day -= timedelta(days=1)
        session = TherapySession(
            case_id=case.id,
            therapist_user_id=therapist.id,
            scheduled_date=day,
            start_time=time(10, 0),
            end_time=time(11, 0),
            mode=SessionMode.HOME,
            status=SessionStatus.CANCELLED,
            cancellation_reason="parent_cancelled_test",
        )
        db.add(session)
        db.commit()
        db.refresh(session)

        rows = attendance_resolution.list_unresolved_attendance_days(
            db, therapist_user_id=therapist.id, from_date=day, to_date=day
        )
        assert any(r["session_id"] == session.id for r in rows)

        ym = f"{day.year}-{day.month:02d}"
        preview = billing.build_month_preview(db, therapist.id, ym)
        assert preview.get("unresolved_attendance_count", 0) >= 1
        kinds = []
        for cg in preview.get("cases") or []:
            for line in cg.get("pending_approval_lines") or []:
                kinds.append(line.get("line_kind"))
        assert "SESSION_CANCELLED_UNEXPLAINED" in kinds or "ATTENDANCE_NEEDS_DISPOSITION" in kinds
    finally:
        db.close()


def test_new_leave_blocked_when_unresolved_days_exist():
    db = SessionLocal()
    try:
        therapist = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
        assignment = db.scalars(
            select(CaseAssignment).where(
                CaseAssignment.therapist_user_id == therapist.id,
                CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
            )
        ).first()
        case = db.get(Case, assignment.case_id)
        day = today_ist() - timedelta(days=5)
        while day.weekday() >= 5:
            day -= timedelta(days=1)
        # Cancelled-without-disposition is a gate reason (not mere SCHEDULED needs-log).
        session = TherapySession(
            case_id=case.id,
            therapist_user_id=therapist.id,
            scheduled_date=day,
            start_time=time(9, 0),
            end_time=time(10, 0),
            mode=SessionMode.HOME,
            status=SessionStatus.CANCELLED,
            cancellation_reason="unexplained_cancel_gate_test",
        )
        db.add(session)
        db.commit()

        with pytest.raises(ValueError, match="disposition"):
            leave_service.create_therapist_leave_request(
                db,
                therapist=therapist,
                start_date=today_ist() + timedelta(days=40),
                end_date=today_ist() + timedelta(days=40),
                case_ids=[case.id],
                service_line="shadow_support",
            )
    finally:
        db.close()


def test_unresolved_attendance_api():
    token = _login("therapist@demo.com")
    r = client.get("/api/v1/leave/unresolved-attendance", headers=_headers(token))
    assert r.status_code == 200
    body = r.json()
    assert "count" in body and "days" in body
    assert isinstance(body["days"], list)
