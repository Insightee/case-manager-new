from __future__ import annotations

from datetime import date, timedelta

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
# Far-future dates avoid same-day duplicate rules and seed collisions in the shared CI DB.
_FRESH_SESSION_BASE = date(2099, 1, 1)


def _fresh_scheduled_session(headers: dict) -> int:
    global _fresh_session_counter
    cases = client.get("/api/v1/cases?assigned=true&page_size=20", headers=headers).json()
    case_items = cases.get("items", cases) if isinstance(cases, dict) else cases
    if not case_items:
        raise AssertionError("No assigned cases for therapist")
    for attempt in range(len(case_items) * 3):
        _fresh_session_counter += 1
        case_id = int(case_items[_fresh_session_counter % len(case_items)]["id"])
        day = (_FRESH_SESSION_BASE + timedelta(days=_fresh_session_counter)).isoformat()
        hour = 8 + (_fresh_session_counter % 10)
        minute = 10 + (_fresh_session_counter % 45)
        start = f"{hour:02d}:{minute:02d}"
        end_hour = hour + ((minute + 29) // 60)
        end_minute = (minute + 29) % 60
        end = f"{end_hour:02d}:{end_minute:02d}"
        created = client.post(
            "/api/v1/sessions",
            headers=headers,
            json={
                "case_id": case_id,
                "therapist_user_id": 0,
                "scheduled_date": day,
                "start_time": start,
                "end_time": end,
                "mode": "HOME",
                "status": "SCHEDULED",
            },
        )
        if created.status_code != 201:
            continue
        session_id = int(created.json()["id"])
        existing = client.get(f"/api/v1/sessions/{session_id}/absence", headers=headers)
        if existing.status_code == 200 and existing.json().get("status") == "none":
            return session_id
    raise AssertionError("Could not allocate a fresh scheduled session for absence tests")


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

    approve = client.post(
        f"/api/v1/sessions/absence/{body['id']}/approve",
        headers=admin_headers,
        json={},
    )
    assert approve.status_code == 200, approve.text
    assert approve.json()["status"] == "APPROVED"

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
    isolated_day = (date(2099, 6, 1)).isoformat()
    cases = client.get("/api/v1/cases?assigned=true&page_size=1", headers=therapist_headers).json()
    case_items = cases.get("items", cases) if isinstance(cases, dict) else cases
    case_id = int(case_items[0]["id"])
    created = client.post(
        "/api/v1/sessions",
        headers=therapist_headers,
        json={
            "case_id": case_id,
            "therapist_user_id": 0,
            "scheduled_date": isolated_day,
            "start_time": "15:20",
            "end_time": "16:20",
            "mode": "HOME",
            "status": "SCHEDULED",
        },
    )
    assert created.status_code == 201, created.text
    session_id = int(created.json()["id"])
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
    from app.core.timezone import today_ist

    therapist_headers = _login("therapist@demo.com")
    today = today_ist().isoformat()
    cases = client.get("/api/v1/cases?assigned=true&page_size=20", headers=therapist_headers).json()
    case_items = cases.get("items", cases) if isinstance(cases, dict) else cases
    session_id = None
    case_id = None
    for idx, case in enumerate(case_items):
        case_id = int(case["id"])
        listed = client.get(
            f"/api/v1/sessions?assigned=true&case_id={case_id}&page_size=50",
            headers=therapist_headers,
        ).json()
        items = listed.get("items", listed) if isinstance(listed, dict) else listed
        for s in items:
            if s.get("scheduled_date") == today and s.get("status") == "SCHEDULED":
                session_id = int(s["id"])
                break
        if session_id:
            break
        created = client.post(
            "/api/v1/sessions",
            headers=therapist_headers,
            json={
                "case_id": case_id,
                "therapist_user_id": 0,
                "scheduled_date": today,
                "start_time": f"{18 + (idx % 2):02d}:{10 + idx:02d}",
                "end_time": f"{19 + (idx % 2):02d}:{10 + idx:02d}",
                "mode": "HOME",
                "status": "SCHEDULED",
            },
        )
        if created.status_code == 201:
            session_id = int(created.json()["id"])
            break
    assert session_id and case_id

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
