from __future__ import annotations

import csv
from datetime import datetime, timedelta
from io import StringIO

import pytest
from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app.main import app
from app.models.case import Case
from app.seed.demo_seed import run as seed_run
from app.tests.conftest import first_meeting_slot, future_meeting_date

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    seed_run()


def _login(email: str) -> str:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "demo123"})
    assert response.status_code == 200
    return response.json()["access_token"]


def _headers(email: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {_login(email)}"}


def _first_bookable_case_id(email: str) -> int:
    response = client.get("/api/v1/meetings/bookable-cases", headers=_headers(email))
    assert response.status_code == 200
    rows = response.json()
    assert rows, "expected at least one bookable case"
    return int(rows[0]["id"])


def _case_manager_id(case_id: int) -> int:
    with SessionLocal() as db:
        case = db.get(Case, case_id)
        assert case is not None and case.case_manager_user_id is not None
        return int(case.case_manager_user_id)


def _create_meeting(
    email: str = "superadmin@demo.com",
    *,
    case_id: int | None = None,
    scheduled_date: str | None = None,
    scheduled_time: str = "10:00:00",
    duration_minutes: int = 30,
    meeting_type: str = "PARENT_MEETING",
):
    payload = {
        "scheduled_date": scheduled_date or future_meeting_date(14),
        "scheduled_time": scheduled_time,
        "duration_minutes": duration_minutes,
        "meeting_type": meeting_type,
    }
    if case_id is not None:
        payload["case_id"] = case_id
    response = client.post("/api/v1/meetings", headers=_headers(email), json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_reschedule_ignores_self_conflict_and_preserves_series_id():
    headers = _headers("superadmin@demo.com")
    case_id = _first_bookable_case_id("superadmin@demo.com")
    slot_date, slot_time = first_meeting_slot(
        client,
        headers,
        [_case_manager_id(case_id)],
        days_ahead=50,
        duration_minutes=30,
        slot_index=0,
    )
    meeting = _create_meeting(
        case_id=case_id,
        scheduled_date=slot_date,
        scheduled_time=slot_time,
        duration_minutes=30,
    )
    shift_time = (
        datetime.strptime(slot_time, "%H:%M:%S") + timedelta(minutes=30)
    ).strftime("%H:%M:%S")

    response = client.post(
        f"/api/v1/meetings/{meeting['id']}/reschedule",
        headers=headers,
        json={
            "scheduled_date": slot_date,
            "scheduled_time": shift_time,
            "duration_minutes": 30,
            "reschedule_reason": "Shifted by 30 minutes",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["old_meeting"]["status"] == "RESCHEDULED"
    assert body["new_meeting"]["status"] == "SCHEDULED"
    assert body["new_meeting"]["rescheduled_from_id"] == meeting["id"]
    assert body["new_meeting"]["series_id"] == meeting["series_id"]


def test_patch_scheduled_date_returns_400():
    case_id = _first_bookable_case_id("superadmin@demo.com")
    meeting = _create_meeting(case_id=case_id, scheduled_date=future_meeting_date(16), scheduled_time="11:00:00")

    response = client.patch(
        f"/api/v1/meetings/{meeting['id']}",
        headers=_headers("superadmin@demo.com"),
        json={"scheduled_date": "2026-09-17"},
    )
    assert response.status_code == 400, response.text
    assert "reschedule" in response.json()["detail"].lower()


def test_cancel_requires_reason_and_succeeds():
    case_id = _first_bookable_case_id("superadmin@demo.com")
    meeting = _create_meeting(case_id=case_id, scheduled_date=future_meeting_date(18), scheduled_time="12:00:00")

    missing = client.post(
        f"/api/v1/meetings/{meeting['id']}/cancel",
        headers=_headers("superadmin@demo.com"),
        json={},
    )
    assert missing.status_code == 400, missing.text

    cancelled = client.post(
        f"/api/v1/meetings/{meeting['id']}/cancel",
        headers=_headers("superadmin@demo.com"),
        json={"reason": "Family requested"},
    )
    assert cancelled.status_code == 200, cancelled.text
    body = cancelled.json()
    assert body["status"] == "CANCELLED"
    assert body["cancel_reason"] == "Family requested"
    assert body["cancelled_at"] is not None


def test_action_upsert_preserves_id_and_status():
    case_id = _first_bookable_case_id("superadmin@demo.com")
    meeting = _create_meeting(case_id=case_id, scheduled_date=future_meeting_date(19), scheduled_time="13:00:00")

    created = client.patch(
        f"/api/v1/meetings/{meeting['id']}",
        headers=_headers("superadmin@demo.com"),
        json={
            "actions": [
                {
                    "title": "Call parent",
                    "owner_role": "admin",
                    "due_date": "2026-09-20",
                    "status": "open",
                },
                {
                    "title": "Review notes",
                    "owner_role": "therapist",
                    "due_date": "2026-09-21",
                    "status": "completed",
                },
            ]
        },
    )
    assert created.status_code == 200, created.text
    created_actions = created.json()["actions"]
    assert len(created_actions) == 2
    first_action_id = created_actions[0]["id"]

    updated = client.patch(
        f"/api/v1/meetings/{meeting['id']}",
        headers=_headers("superadmin@demo.com"),
        json={
            "actions": [
                {
                    "id": first_action_id,
                    "title": "Call parent again",
                    "owner_role": "admin",
                    "due_date": "2026-09-22",
                },
                {
                    "title": "Prepare handoff",
                    "owner_role": "case_manager",
                    "due_date": "2026-09-23",
                },
            ]
        },
    )
    assert updated.status_code == 200, updated.text
    actions = updated.json()["actions"]
    assert len(actions) == 2
    first = next(item for item in actions if item["id"] == first_action_id)
    assert first["status"] == "open"
    assert first["title"] == "Call parent again"
    assert all(item["title"] != "Review notes" for item in actions)


def test_get_meeting_returns_404_for_other_case_manager():
    case_id = _first_bookable_case_id("casemanager@demo.com")
    meeting = _create_meeting(
        email="casemanager@demo.com",
        case_id=case_id,
        scheduled_date=future_meeting_date(20),
        scheduled_time="14:00:00",
    )

    response = client.get(
        f"/api/v1/meetings/{meeting['id']}",
        headers=_headers("shadowcm@demo.com"),
    )
    assert response.status_code == 404, response.text


def test_export_status_filter_matches_list():
    headers = _headers("superadmin@demo.com")
    listed = client.get("/api/v1/meetings?status=SCHEDULED", headers=headers)
    assert listed.status_code == 200, listed.text
    list_ids = {row["id"] for row in listed.json()}

    exported = client.get("/api/v1/meetings/export?format=csv&status=SCHEDULED", headers=headers)
    assert exported.status_code == 200, exported.text

    reader = csv.DictReader(StringIO(exported.text))
    export_ids = {int(row["Meeting ID"]) for row in reader}
    assert export_ids == list_ids
