from __future__ import annotations

import pytest
from datetime import date, time
from fastapi.testclient import TestClient

from app.main import app
from app.seed.demo_seed import run as seed_run
from app.tests.conftest import api_items

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    seed_run()


def _login(email: str) -> str:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "demo123"})
    assert r.status_code == 200
    return r.json()["access_token"]


def test_booking_validation_and_flow():
    token = _login("superadmin@demo.com")
    headers = {"Authorization": f"Bearer {token}"}

    # Fetch bookable cases
    cases_res = client.get("/api/v1/meetings/bookable-cases", headers=headers)
    assert cases_res.status_code == 200
    cases = cases_res.json()
    assert len(cases) > 0
    case_id = cases[0]["id"]

    # Book meeting: Invalid duration
    res = client.post(
        "/api/v1/meetings",
        headers=headers,
        json={
            "case_id": case_id,
            "scheduled_date": "2026-06-20",
            "scheduled_time": "10:00:00",
            "duration_minutes": 50,  # invalid
            "meeting_type": "PARENT_MEETING",
            "platform": "GOOGLE_MEET",
            "meeting_url": "https://meet.google.com/abc-defg-hij"
        }
    )
    assert res.status_code == 400
    assert "duration must be 30, 45, 60, or 90" in res.json()["detail"]

    # Book meeting: Invalid url for platform
    res = client.post(
        "/api/v1/meetings",
        headers=headers,
        json={
            "case_id": case_id,
            "scheduled_date": "2026-06-20",
            "scheduled_time": "10:00:00",
            "duration_minutes": 60,
            "meeting_type": "PARENT_MEETING",
            "platform": "ZOOM",
            "meeting_url": "https://meet.google.com/abc-def-hij"  # not zoom
        }
    )
    assert res.status_code == 400
    assert "Invalid Zoom URL" in res.json()["detail"]

    # Book meeting: OTHER type missing reason
    res = client.post(
        "/api/v1/meetings",
        headers=headers,
        json={
            "case_id": case_id,
            "scheduled_date": "2026-06-20",
            "scheduled_time": "10:00:00",
            "duration_minutes": 60,
            "meeting_type": "OTHER",
            "other_reason": ""  # empty
        }
    )
    assert res.status_code == 400
    assert "reason must be provided" in res.json()["detail"]

    # Book meeting: Successful booking
    res = client.post(
        "/api/v1/meetings",
        headers=headers,
        json={
            "case_id": case_id,
            "scheduled_date": "2026-06-20",
            "scheduled_time": "10:00:00",
            "duration_minutes": 60,
            "meeting_type": "PARENT_MEETING",
            "platform": "GOOGLE_MEET",
            "meeting_url": "https://meet.google.com/abc-defg-hij"
        }
    )
    assert res.status_code == 201
    meeting = res.json()
    assert meeting["duration_minutes"] == 60
    assert meeting["meeting_type"] == "PARENT_MEETING"

    # Try double booking CM on same slot
    res_db = client.post(
        "/api/v1/meetings",
        headers=headers,
        json={
            "case_id": case_id,
            "scheduled_date": "2026-06-20",
            "scheduled_time": "10:30:00",  # overlaps with 10:00 - 11:00
            "duration_minutes": 30,
            "meeting_type": "PARENT_MEETING"
        }
    )
    assert res_db.status_code == 400
    assert "Double booking error" in res_db.json()["detail"]


def test_availability_engine():
    token = _login("superadmin@demo.com")
    headers = {"Authorization": f"Bearer {token}"}

    # Query availability for a case manager
    res = client.get(
        "/api/v1/meetings/availability",
        headers=headers,
        params={
            "target_date": "2026-06-20",
            "case_manager_id": 1,
            "duration_minutes": 30
        }
    )
    assert res.status_code == 200
    data = res.json()
    assert "slots" in data
    assert len(data["slots"]) == 9  # 9 slots from 9:00 to 17:00


def test_reschedule_flow():
    token = _login("superadmin@demo.com")
    headers = {"Authorization": f"Bearer {token}"}

    # Create initial meeting
    res = client.post(
        "/api/v1/meetings",
        headers=headers,
        json={
            "scheduled_date": "2026-06-25",
            "scheduled_time": "14:00:00",
            "duration_minutes": 45,
            "meeting_type": "IEP_MEETING"
        }
    )
    assert res.status_code == 201
    mid = res.json()["id"]

    # Reschedule meeting
    res_r = client.post(
        f"/api/v1/meetings/{mid}/reschedule",
        headers=headers,
        json={
            "scheduled_date": "2026-06-26",
            "scheduled_time": "15:00:00",
            "duration_minutes": 45,
            "reschedule_reason": "Parent conflict"
        }
    )
    assert res_r.status_code == 200
    details = res_r.json()
    assert details["old_meeting"]["status"] == "RESCHEDULED"
    assert details["new_meeting"]["status"] == "SCHEDULED"
    assert details["new_meeting"]["rescheduled_from_id"] == mid

    listed = client.get("/api/v1/meetings", headers=headers)
    assert listed.status_code == 200
    ids = [row["id"] for row in listed.json()]
    assert mid not in ids, "Rescheduled meeting should not appear in default list"
    assert details["new_meeting"]["id"] in ids


def test_other_meeting_type_saves_custom_reason():
    token = _login("superadmin@demo.com")
    headers = {"Authorization": f"Bearer {token}"}

    res = client.post(
        "/api/v1/meetings",
        headers=headers,
        json={
            "scheduled_date": "2026-06-27",
            "scheduled_time": "12:00:00",
            "duration_minutes": 30,
            "meeting_type": "OTHER",
            "other_reason": "School coordinator sync",
        },
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["other_reason"] == "School coordinator sync"
    assert body["title"] == "School coordinator sync"


def test_other_meeting_type_accepts_title_fallback():
    token = _login("superadmin@demo.com")
    headers = {"Authorization": f"Bearer {token}"}

    res = client.post(
        "/api/v1/meetings",
        headers=headers,
        json={
            "scheduled_date": "2026-06-27",
            "scheduled_time": "13:00:00",
            "duration_minutes": 30,
            "meeting_type": "OTHER",
            "title": "External specialist call",
        },
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["other_reason"] == "External specialist call"
    assert body["title"] == "External specialist call"

    token = _login("superadmin@demo.com")
    headers = {"Authorization": f"Bearer {token}"}

    # Create meeting
    res = client.post(
        "/api/v1/meetings",
        headers=headers,
        json={
            "scheduled_date": "2026-06-28",
            "scheduled_time": "11:00:00",
            "duration_minutes": 30,
            "meeting_type": "PROGRESS_REVIEW"
        }
    )
    mid = res.json()["id"]

    # Try to mark COMPLETED without outcomes/summary
    res_patch = client.patch(
        f"/api/v1/meetings/{mid}",
        headers=headers,
        json={
            "status": "COMPLETED",
            "notes_outcome": "",
            "notes_summary": ""
        }
    )
    assert res_patch.status_code == 400
    assert "Meeting Outcome and Discussion Summary are required" in res_patch.json()["detail"]

    # Complete meeting with valid notes
    res_patch_ok = client.patch(
        f"/api/v1/meetings/{mid}",
        headers=headers,
        json={
            "status": "COMPLETED",
            "notes_outcome": "RESOLVED",
            "notes_summary": "Discussed client behavior changes, actions agreed."
        }
    )
    assert res_patch_ok.status_code == 200
    meeting = res_patch_ok.json()
    assert meeting["status"] == "COMPLETED"
    assert meeting["notes_outcome"] == "RESOLVED"


def test_meeting_actions_sync_and_dashboard():
    token = _login("superadmin@demo.com")
    headers = {"Authorization": f"Bearer {token}"}

    # Create meeting
    res = client.post(
        "/api/v1/meetings",
        headers=headers,
        json={
            "scheduled_date": "2026-07-02",
            "scheduled_time": "12:00:00",
            "duration_minutes": 30,
            "meeting_type": "THERAPIST_SUPPORT"
        }
    )
    mid = res.json()["id"]

    # Sync actions in notes update
    res_patch = client.patch(
        f"/api/v1/meetings/{mid}",
        headers=headers,
        json={
            "notes_outcome": "FOLLOW_UP_REQUIRED",
            "notes_summary": "Therapist needs support with materials.",
            "actions": [
                {
                    "title": "Prepare visual schedule materials",
                    "owner_role": "therapist",
                    "due_date": "2026-07-05",
                    "status": "open"
                },
                {
                    "title": "Review IEP goals",
                    "owner_role": "admin",
                    "due_date": "2026-07-06",
                    "status": "open"
                }
            ]
        }
    )
    assert res_patch.status_code == 200
    meeting = res_patch.json()
    assert len(meeting["actions"]) == 2

    # Fetch open actions from dashboard
    res_act = client.get("/api/v1/meetings/actions", headers=headers)
    assert res_act.status_code == 200
    actions = res_act.json()
    assert len(actions) >= 2


def test_meetings_calendar_personal_scope():
    token = _login("superadmin@demo.com")
    headers = {"Authorization": f"Bearer {token}"}

    res = client.get(
        "/api/v1/meetings/calendar",
        headers=headers,
        params={"from_date": "2026-01-01", "to_date": "2026-12-31"},
    )
    assert res.status_code == 200
    data = res.json()
    assert "cm_meetings" in data
    assert isinstance(data["cm_meetings"], list)


def test_meeting_exports():
    token = _login("superadmin@demo.com")
    headers = {"Authorization": f"Bearer {token}"}

    # Export Excel
    excel_res = client.get("/api/v1/meetings/export?format=excel", headers=headers)
    assert excel_res.status_code == 200
    assert excel_res.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    # Export CSV
    csv_res = client.get("/api/v1/meetings/export?format=csv", headers=headers)
    assert csv_res.status_code == 200
    assert csv_res.headers["content-type"] == "text/csv; charset=utf-8"

    # Export PDF
    pdf_res = client.get("/api/v1/meetings/export?format=pdf", headers=headers)
    assert pdf_res.status_code == 200
    assert pdf_res.headers["content-type"] == "application/pdf"
