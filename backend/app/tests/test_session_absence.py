from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    from app.seed.demo_seed import run as seed_run

    seed_run()


def _login(email: str) -> dict[str, str]:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "demo123"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _therapist_scheduled_session(headers: dict) -> int:
    r = client.get("/api/v1/sessions?assigned=true&page_size=50", headers=headers)
    assert r.status_code == 200
    items = r.json().get("items", r.json()) if isinstance(r.json(), dict) else r.json()
    for s in items:
        if s.get("status") == "SCHEDULED":
            return int(s["id"])
    today = date.today().isoformat()
    cases = client.get("/api/v1/cases?assigned=true&page_size=1", headers=headers).json()
    case_items = cases.get("items", cases) if isinstance(cases, dict) else cases
    case_id = int(case_items[0]["id"])
    created = client.post(
        "/api/v1/sessions",
        headers=headers,
        json={
            "case_id": case_id,
            "therapist_user_id": 0,
            "scheduled_date": today,
            "start_time": "10:00",
            "end_time": "11:00",
            "mode": "HOME",
            "status": "SCHEDULED",
        },
    )
    assert created.status_code == 201, created.text
    return int(created.json()["id"])


_fresh_session_counter = 0


def _absence_allowed_day() -> date:
    """Match leave_migration.validate_child_absence_date + session create (`today_ist`).

    After the migration window closes, only today's scheduled visit may receive a
    child-absence log. Far-future fixture dates (e.g. 2099) correctly fail validation
    and must not be used to bypass production rules.
    """
    from app.core.timezone import today_ist

    return today_ist()


def _fresh_scheduled_session(headers: dict) -> int:
    """Allocate a unique SCHEDULED session on the absence-allowed day (today).

    Inserts via DB so tests are not blocked by therapist API rules that allow only one
    walk-in/session create per case-day once a pending child absence exists. Absence
    API validation still enforces the production no-future-date rule.
    """
    global _fresh_session_counter
    from datetime import time as dt_time

    from sqlalchemy import select

    from app.core.database import SessionLocal
    from app.models.session import Session as TherapySession
    from app.models.session import SessionMode, SessionStatus
    from app.services.leave_dates_service import active_absence_on_case_day, active_leave_for_case_day

    me = client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200, me.text
    therapist_id = int(me.json()["id"])

    cases = client.get("/api/v1/cases?assigned=true&page_size=20", headers=headers).json()
    case_items = cases.get("items", cases) if isinstance(cases, dict) else cases
    if not case_items:
        raise AssertionError("No assigned cases for therapist")

    day = _absence_allowed_day()
    db = SessionLocal()
    try:
        for _attempt in range(24):
            _fresh_session_counter += 1
            case_id = int(case_items[_fresh_session_counter % len(case_items)]["id"])
            if active_absence_on_case_day(db, case_id, day) or active_leave_for_case_day(
                db, therapist_id, case_id, day
            ):
                from app.models.assignment import CaseAssignment, CaseAssignmentStatus
                from app.models.case import BillingType, Case, CaseDayType, CaseStatus, CompensationMode
                from app.models.child import Child

                child = db.scalars(select(Child).limit(1)).first()
                if not child:
                    continue
                fresh_case = Case(
                    case_code=f"ABSENCE-ISO-{_fresh_session_counter}",
                    child_id=child.id,
                    service_type="Homecare",
                    product_module="homecare",
                    status=CaseStatus.ACTIVE,
                    billing_type=BillingType.PER_SESSION,
                    compensation_mode=CompensationMode.FIXED_LUMP,
                    day_type=CaseDayType.FULL_DAY,
                )
                db.add(fresh_case)
                db.flush()
                db.add(
                    CaseAssignment(
                        case_id=fresh_case.id,
                        therapist_user_id=therapist_id,
                        status=CaseAssignmentStatus.ACTIVE,
                        start_date=day,
                    )
                )
                db.flush()
                case_id = fresh_case.id
            hour = 6 + (_fresh_session_counter % 14)
            minute = (_fresh_session_counter * 7) % 50
            end_minute = minute + 25
            end_hour = hour + (1 if end_minute >= 60 else 0)
            session = TherapySession(
                case_id=case_id,
                therapist_user_id=therapist_id,
                scheduled_date=day,
                start_time=dt_time(hour, minute),
                end_time=dt_time(end_hour, end_minute % 60),
                mode=SessionMode.HOME,
                status=SessionStatus.SCHEDULED,
            )
            db.add(session)
            db.flush()
            # Isolate case+day so manual/walk-in conflict lookup prefers this row
            # (SCHEDULED ranks above CLIENT_ABSENT; leftover siblings caused EXISTING_SESSION_FOR_DATE).
            siblings = db.scalars(
                select(TherapySession).where(
                    TherapySession.case_id == case_id,
                    TherapySession.therapist_user_id == therapist_id,
                    TherapySession.scheduled_date == day,
                    TherapySession.id != session.id,
                    TherapySession.status.notin_(
                        (SessionStatus.CANCELLED, SessionStatus.RESCHEDULED)
                    ),
                )
            ).all()
            for sib in siblings:
                sib.status = SessionStatus.CANCELLED
            db.commit()
            db.refresh(session)
            session_id = int(session.id)
            existing = client.get(f"/api/v1/sessions/{session_id}/absence", headers=headers)
            if existing.status_code == 200 and existing.json().get("status") == "none":
                return session_id
        raise AssertionError("Could not allocate a fresh scheduled session for absence tests")
    finally:
        db.close()


def test_child_absent_admin_approve_parent_notification():
    therapist_headers = _login("therapist@demo.com")
    session_id = _fresh_scheduled_session(therapist_headers)
    create = client.post(
        f"/api/v1/sessions/{session_id}/absence",
        headers=therapist_headers,
        json={"absence_type": "CLIENT_ABSENT", "reason": "Unwell"},
    )
    assert create.status_code == 201, create.text
    body = create.json()
    assert body["status"] == "PENDING_APPROVAL"
    assert body["absence_type"] == "CLIENT_ABSENT"

    parent_headers = _login("parent@demo.com")
    inbox_before = client.get("/api/v1/parent/absence-requests", headers=parent_headers)
    assert inbox_before.status_code == 200
    assert body["id"] not in {item["id"] for item in inbox_before.json().get("items", [])}

    parent_approve = client.post(
        f"/api/v1/sessions/absence/{body['id']}/approve",
        headers=parent_headers,
        json={},
    )
    assert parent_approve.status_code == 403

    admin_headers = _login("superadmin@demo.com")
    child_queue = client.get("/api/v1/leave/child-absence", headers=admin_headers)
    assert child_queue.status_code == 200
    assert body["id"] in {item["id"] for item in child_queue.json().get("items", [])}

    with patch("app.services.email.parent_mail.send_parent_email") as send_email:
        approve = client.post(
            f"/api/v1/sessions/absence/{body['id']}/approve",
            headers=admin_headers,
            json={},
        )
    assert approve.status_code == 200, approve.text
    assert approve.json()["status"] == "APPROVED"
    send_email.assert_called()

    inbox_after = client.get("/api/v1/parent/absence-requests", headers=parent_headers)
    assert inbox_after.status_code == 200
    assert body["id"] in {item["id"] for item in inbox_after.json().get("items", [])}

    sessions = client.get("/api/v1/sessions?page_size=100", headers=therapist_headers)
    assert sessions.status_code == 200
    items = sessions.json().get("items", sessions.json()) if isinstance(sessions.json(), dict) else sessions.json()
    row = next((s for s in items if s["id"] == session_id), None)
    assert row is not None
    assert row["status"] in ("CLIENT_ABSENT", "CANCELLED")


def test_child_absent_admin_reject_notifies_therapist():
    therapist_headers = _login("therapist@demo.com")
    session_id = _fresh_scheduled_session(therapist_headers)
    create = client.post(
        f"/api/v1/sessions/{session_id}/absence",
        headers=therapist_headers,
        json={"absence_type": "CLIENT_ABSENT", "reason": "Travel"},
    )
    assert create.status_code == 201, create.text
    req_id = create.json()["id"]

    admin_headers = _login("superadmin@demo.com")
    reject = client.post(
        f"/api/v1/sessions/absence/{req_id}/reject",
        headers=admin_headers,
        json={"review_note": "Session was held as scheduled"},
    )
    assert reject.status_code == 200, reject.text
    assert reject.json()["status"] == "REJECTED"
    assert reject.json()["review_note"] == "Session was held as scheduled"

    sess = client.get(f"/api/v1/sessions/{session_id}", headers=therapist_headers)
    assert sess.status_code == 200
    assert sess.json()["status"] == "SCHEDULED"


def test_therapist_leave_admin_approve():
    therapist_headers = _login("therapist@demo.com")
    session_id = _therapist_scheduled_session(therapist_headers)
    create = client.post(
        f"/api/v1/sessions/{session_id}/absence",
        headers=therapist_headers,
        json={
            "absence_type": "THERAPIST_LEAVE",
            "leave_billing_category": "UNPAID",
            "reason": "Personal",
        },
    )
    assert create.status_code == 201, create.text
    req_id = create.json()["id"]

    admin_headers = _login("superadmin@demo.com")
    pending = client.get("/api/v1/sessions/absence/pending", headers=admin_headers)
    assert pending.status_code == 200
    assert req_id in {i["id"] for i in pending.json().get("items", [])}

    approve = client.post(
        f"/api/v1/sessions/absence/{req_id}/approve",
        headers=admin_headers,
        json={"review_note": "Approved"},
    )
    assert approve.status_code == 200
    assert approve.json()["status"] == "APPROVED"


def test_absence_duplicate_returns_structured_409():
    therapist_headers = _login("therapist@demo.com")
    session_id = _fresh_scheduled_session(therapist_headers)
    payload = {"absence_type": "CLIENT_ABSENT", "reason": "Unwell"}
    first = client.post(f"/api/v1/sessions/{session_id}/absence", headers=therapist_headers, json=payload)
    assert first.status_code == 201, first.text
    second = client.post(f"/api/v1/sessions/{session_id}/absence", headers=therapist_headers, json=payload)
    assert second.status_code == 409, second.text
    detail = second.json()["detail"]
    assert detail["existing"] is True
    assert detail["absence_request"]["session_id"] == session_id
    assert detail["status"] == "pending"


def test_get_absence_by_session_id():
    therapist_headers = _login("therapist@demo.com")
    session_id = _fresh_scheduled_session(therapist_headers)
    empty = client.get(f"/api/v1/sessions/{session_id}/absence", headers=therapist_headers)
    assert empty.status_code == 200
    assert empty.json()["status"] == "none"

    create = client.post(
        f"/api/v1/sessions/{session_id}/absence",
        headers=therapist_headers,
        json={"absence_type": "CLIENT_ABSENT", "reason": "Travel"},
    )
    assert create.status_code == 201
    pending = client.get(f"/api/v1/sessions/{session_id}/absence", headers=therapist_headers)
    assert pending.status_code == 200
    body = pending.json()
    assert body["status"] == "pending"
    assert body["absence_request"]["id"] == create.json()["id"]


def test_absence_does_not_create_in_progress_or_daily_log():
    from sqlalchemy import select

    from app.core.database import SessionLocal
    from app.models.daily_log import DailyLog

    therapist_headers = _login("therapist@demo.com")
    session_id = _fresh_scheduled_session(therapist_headers)
    create = client.post(
        f"/api/v1/sessions/{session_id}/absence",
        headers=therapist_headers,
        json={"absence_type": "CLIENT_ABSENT", "reason": "Sick"},
    )
    assert create.status_code == 201, create.text
    sess = client.get(f"/api/v1/sessions/{session_id}", headers=therapist_headers)
    assert sess.status_code == 200
    row = sess.json()
    assert row["status"] == "SCHEDULED"
    logs = client.get("/api/v1/daily-logs", headers=therapist_headers)
    assert logs.status_code == 200
    items = logs.json() if isinstance(logs.json(), list) else logs.json().get("items", [])
    assert not any(l.get("session_id") == session_id and l.get("id", 0) > 0 for l in items)
    db = SessionLocal()
    try:
        persisted_log = db.scalars(select(DailyLog).where(DailyLog.session_id == session_id)).first()
        assert persisted_log is None
    finally:
        db.close()


def test_pending_absence_excludes_session_from_workspace_queues():
    therapist_headers = _login("therapist@demo.com")
    session_id = _fresh_scheduled_session(therapist_headers)
    create = client.post(
        f"/api/v1/sessions/{session_id}/absence",
        headers=therapist_headers,
        json={"absence_type": "CLIENT_ABSENT", "reason": "Unwell"},
    )
    assert create.status_code == 201, create.text

    ws = client.get("/api/v1/therapist/sessions/workspace", headers=therapist_headers)
    assert ws.status_code == 200
    body = ws.json()
    upcoming_ids = {int(s["id"]) for s in body.get("upcoming", [])}
    needs_ids = {int(s["id"]) for s in body.get("needs_log", [])}
    assert session_id not in upcoming_ids
    assert session_id not in needs_ids

    logs = client.get("/api/v1/daily-logs", headers=therapist_headers)
    assert logs.status_code == 200
    items = logs.json() if isinstance(logs.json(), list) else []
    virtual = [l for l in items if l.get("session_id") == session_id and l.get("id", 0) < 0]
    assert virtual
    assert virtual[0]["attendance_status"] == "CLIENT_ABSENT"


def test_cannot_start_session_with_pending_child_absence():
    therapist_headers = _login("therapist@demo.com")
    session_id = _fresh_scheduled_session(therapist_headers)
    create = client.post(
        f"/api/v1/sessions/{session_id}/absence",
        headers=therapist_headers,
        json={"absence_type": "CLIENT_ABSENT", "reason": "Unwell"},
    )
    assert create.status_code == 201, create.text

    start = client.post(f"/api/v1/sessions/{session_id}/start", headers=therapist_headers, json={})
    assert start.status_code == 400, start.text
    detail = start.json()["detail"]
    assert detail["code"] == "PENDING_CHILD_ABSENCE"
    assert "child absence" in detail["message"].lower()


def test_walk_in_create_blocked_with_pending_child_absence_message():
    therapist_headers = _login("therapist@demo.com")
    session_id = _fresh_scheduled_session(therapist_headers)
    sess = client.get(f"/api/v1/sessions/{session_id}", headers=therapist_headers)
    assert sess.status_code == 200
    case_id = int(sess.json()["case_id"])
    today = sess.json()["scheduled_date"]

    create = client.post(
        f"/api/v1/sessions/{session_id}/absence",
        headers=therapist_headers,
        json={"absence_type": "CLIENT_ABSENT", "reason": "Unwell"},
    )
    assert create.status_code == 201, create.text

    walk_in = client.post(
        "/api/v1/sessions",
        headers=therapist_headers,
        json={
            "case_id": case_id,
            "therapist_user_id": 0,
            "scheduled_date": today,
            "start_time": "10:00",
            "end_time": "11:00",
            "mode": "HOME",
            "status": "SCHEDULED",
        },
    )
    assert walk_in.status_code == 409, walk_in.text
    detail = walk_in.json()["detail"]
    assert detail["code"] == "PENDING_CHILD_ABSENCE"
    assert detail["recommended_action"] == "blocked_absence"
    assert "scheduled session already exists" not in detail["message"].lower()
    assert "child absence" in detail["message"].lower()


def test_manual_log_blocked_when_child_marked_absent():
    therapist_headers = _login("therapist@demo.com")
    admin_headers = _login("superadmin@demo.com")
    session_id = _fresh_scheduled_session(therapist_headers)
    create = client.post(
        f"/api/v1/sessions/{session_id}/absence",
        headers=therapist_headers,
        json={"absence_type": "CLIENT_ABSENT", "reason": "Unwell"},
    )
    assert create.status_code == 201, create.text
    req_id = create.json()["id"]
    approve = client.post(
        f"/api/v1/sessions/absence/{req_id}/approve",
        headers=admin_headers,
        json={},
    )
    assert approve.status_code == 200, approve.text

    sess = client.get(f"/api/v1/sessions/{session_id}", headers=therapist_headers)
    assert sess.status_code == 200
    body = sess.json()
    scheduled_date = body["scheduled_date"]
    case_id = body["case_id"]

    manual = client.post(
        "/api/v1/sessions/manual",
        headers=therapist_headers,
        json={
            "case_id": case_id,
            "scheduled_date": scheduled_date,
            "actual_start_at": f"{scheduled_date}T10:00:00Z",
            "actual_end_at": f"{scheduled_date}T11:00:00Z",
            "mode": "HOME",
        },
    )
    assert manual.status_code == 409, manual.text
    detail = manual.json()["detail"]
    assert detail["code"] == "CHILD_MARKED_ABSENT"
    assert detail["recommended_action"] == "blocked_absence"
    assert "marked absent" in detail["message"].lower()


def test_child_absence_backfill_creates_session_without_prior_booking():
    from app.services import leave_migration_service as migration

    if not migration.is_migration_window_active():
        pytest.skip("Migration window closed")

    therapist_headers = _login("therapist@demo.com")
    cases = client.get("/api/v1/cases?assigned=true&page_size=1", headers=therapist_headers).json()
    case_items = cases.get("items", cases) if isinstance(cases, dict) else cases
    assert case_items
    case_id = int(case_items[0]["id"])
    backfill_day = "2026-07-12"

    create = client.post(
        "/api/v1/sessions/child-absence/backfill",
        headers=therapist_headers,
        json={
            "case_id": case_id,
            "scheduled_date": backfill_day,
            "reason": "July backfill absence",
        },
    )
    assert create.status_code == 201, create.text
    body = create.json()
    assert body["absence_type"] == "CLIENT_ABSENT"
    assert body["status"] == "PENDING_APPROVAL"
    assert body["is_retroactive"] is True
    assert body["is_migration_reentry"] is True
    assert body["scheduled_date"] == backfill_day
    assert body["session_id"] > 0


def test_today_for_absence_lists_scheduled_visit():
    therapist_headers = _login("therapist@demo.com")
    session_id = _fresh_scheduled_session(therapist_headers)
    sess = client.get(f"/api/v1/sessions/{session_id}", headers=therapist_headers)
    assert sess.status_code == 200
    case_id = int(sess.json()["case_id"])

    listed = client.get(
        f"/api/v1/sessions/absence/today-sessions?case_id={case_id}",
        headers=therapist_headers,
    )
    assert listed.status_code == 200, listed.text
    ids = {int(item["id"]) for item in listed.json().get("items", [])}
    assert session_id in ids


def test_child_absence_blocked_while_session_in_progress():
    therapist_headers = _login("therapist@demo.com")
    session_id = _fresh_scheduled_session(therapist_headers)
    start = client.post(f"/api/v1/sessions/{session_id}/start", headers=therapist_headers, json={})
    assert start.status_code == 200, start.text
    try:
        blocked = client.post(
            f"/api/v1/sessions/{session_id}/absence",
            headers=therapist_headers,
            json={"absence_type": "CLIENT_ABSENT", "reason": "Unwell"},
        )
        assert blocked.status_code == 409, blocked.text
        detail = blocked.json()["detail"]
        assert detail["code"] == "SESSION_IN_PROGRESS"
    finally:
        cancel = client.post(f"/api/v1/sessions/{session_id}/cancel", headers=therapist_headers, json={})
        if cancel.status_code != 200:
            client.post(f"/api/v1/sessions/{session_id}/end", headers=therapist_headers, json={})


def test_child_absence_replace_pending_log():
    from datetime import datetime, timezone

    from app.core.database import SessionLocal
    from app.models.daily_log import AttendanceStatus, DailyLog, LogApprovalStatus
    from app.models.session import Session as TherapySession
    from app.models.session import SessionStatus

    therapist_headers = _login("therapist@demo.com")
    session_id = _fresh_scheduled_session(therapist_headers)

    db = SessionLocal()
    try:
        session = db.get(TherapySession, session_id)
        assert session is not None
        session.status = SessionStatus.COMPLETED
        session.actual_start_at = datetime.now(timezone.utc)
        session.actual_end_at = datetime.now(timezone.utc)
        log = DailyLog(
            session_id=session_id,
            attendance_status=AttendanceStatus.PRESENT.value,
            activities_done="Therapist worked on goals during visit today.",
            approval_status=LogApprovalStatus.PENDING.value,
            submitted_at=datetime.now(timezone.utc),
        )
        db.add(log)
        db.commit()
    finally:
        db.close()

    blocked = client.post(
        f"/api/v1/sessions/{session_id}/absence",
        headers=therapist_headers,
        json={"absence_type": "CLIENT_ABSENT", "reason": "Actually absent"},
    )
    assert blocked.status_code == 409, blocked.text
    detail = blocked.json()["detail"]
    assert detail["code"] == "LOG_EXISTS_FOR_DAY"
    assert detail["can_replace_log"] is True

    replaced = client.post(
        f"/api/v1/sessions/{session_id}/absence",
        headers=therapist_headers,
        json={
            "absence_type": "CLIENT_ABSENT",
            "reason": "Actually absent",
            "confirm_replace_log": True,
        },
    )
    assert replaced.status_code == 201, replaced.text
    assert replaced.json()["absence_type"] == "CLIENT_ABSENT"

    db = SessionLocal()
    try:
        session = db.get(TherapySession, session_id)
        assert session is not None
        assert session.status in (SessionStatus.SCHEDULED, SessionStatus.CANCELLED)
        assert session.daily_log is None
    finally:
        db.close()


def test_admin_child_absence_list_paginated_with_search():
    admin_headers = _login("superadmin@demo.com")
    page1 = client.get("/api/v1/leave/child-absence?page=1&page_size=5", headers=admin_headers)
    assert page1.status_code == 200, page1.text
    payload = page1.json()
    assert isinstance(payload, dict)
    assert "items" in payload
    assert "total" in payload
    assert "counts" in payload

    junk = client.get(
        "/api/v1/leave/child-absence?page=1&search=adsf",
        headers=admin_headers,
    )
    assert junk.status_code == 200, junk.text
    assert junk.json()["total"] >= 0

    first = (payload.get("items") or [{}])[0]
    child_name = (first.get("child_name") or "").strip()
    if child_name:
        token = child_name.split()[0]
        if len(token) >= 2:
            by_child = client.get(
                f"/api/v1/leave/child-absence?page=1&search={token}",
                headers=admin_headers,
            )
            assert by_child.status_code == 200, by_child.text
            assert by_child.json()["total"] >= 1

