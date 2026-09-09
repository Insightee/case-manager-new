from __future__ import annotations

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.database import SessionLocal
from app.core.timezone import now_ist
from app.main import app
from app.models.case_manager_meeting import CaseManagerMeeting, MeetingStatus
from app.models.notification import Notification
from app.seed.demo_seed import run as seed_run
from app.tests.conftest import future_meeting_date, meeting_slot_near_minutes_ahead
from app.services.cm_meeting_service import meeting_participant_user_ids, send_due_meeting_reminders

client = TestClient(app)


def _demo_cm_user_id() -> int:
    from app.models.case import Case

    with SessionLocal() as db:
        case = db.get(Case, _bookable_case_id())
        assert case is not None
        return int(case.case_manager_user_id)


@pytest.fixture(autouse=True)
def _fresh_reminder_calendar():
    _clear_cm_meetings_today(_demo_cm_user_id())
    _set_demo_cm_min_notice(minutes=0)
    yield


def _clear_cm_meetings_today(cm_user_id: int) -> None:
    from sqlalchemy import select

    from app.models.case_manager_meeting import CaseManagerMeeting, MeetingStatus

    today = now_ist().date()
    with SessionLocal() as db:
        meetings = list(
            db.scalars(
                select(CaseManagerMeeting).where(
                    CaseManagerMeeting.case_manager_user_id == cm_user_id,
                    CaseManagerMeeting.scheduled_date == today,
                    CaseManagerMeeting.status == MeetingStatus.SCHEDULED,
                )
            ).all()
        )
        for meeting in meetings:
            meeting.status = MeetingStatus.CANCELLED
            meeting.cancel_reason = "test cleanup"
        db.commit()


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    seed_run()
    _set_demo_cm_min_notice(minutes=0)
    _clear_cm_meetings_today(_demo_cm_user_id())


def _set_demo_cm_min_notice(*, minutes: int) -> None:
    from app.core.database import SessionLocal
    from app.models.case import Case

    headers = _headers("superadmin@demo.com")
    with SessionLocal() as db:
        case = db.get(Case, _bookable_case_id())
        assert case is not None
        cm_user_id = case.case_manager_user_id

    res = client.put(
        f"/api/v1/users/{cm_user_id}/availability",
        headers=headers,
        json={
            "rules": [
                {
                    "weekday": weekday_index,
                    "start_time": "10:00",
                    "end_time": "19:00",
                    "slot_granularity_minutes": 30,
                }
                for weekday_index in range(5)
            ],
            "exceptions": [],
            "booking_policy": {
                "min_notice_minutes": minutes,
                "max_days_ahead": 60,
                "buffer_minutes": 0,
                "allowed_durations": [30, 45, 60, 90],
            },
        },
    )
    assert res.status_code == 200, res.text


def _login(email: str) -> str:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "demo123"})
    assert response.status_code == 200
    return response.json()["access_token"]


def _headers(email: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {_login(email)}"}


def _bookable_case_id(email: str = "superadmin@demo.com") -> int:
    response = client.get("/api/v1/meetings/bookable-cases", headers=_headers(email))
    assert response.status_code == 200, response.text
    rows = response.json()
    assert rows, "expected at least one bookable case"
    return int(rows[0]["id"])


def _future_payload(minutes_ahead: int) -> dict[str, str | int]:
    case_id = _bookable_case_id()
    from app.core.database import SessionLocal
    from app.models.case import Case

    with SessionLocal() as db:
        case = db.get(Case, case_id)
        assert case is not None
        cm_user_id = case.case_manager_user_id

    return {
        "case_id": case_id,
        "invite_client": False,
        **meeting_slot_near_minutes_ahead(
            client,
            _headers("superadmin@demo.com"),
            [cm_user_id],
            minutes_ahead=minutes_ahead,
        ),
    }


def _reminder_notification_count(db, meeting_id: int) -> int:
    return int(
        db.scalar(
            select(func.count(Notification.id)).where(
                Notification.entity_type == "cm_meeting",
                Notification.entity_id == meeting_id,
                Notification.body.like(f"%meeting_reminder:{meeting_id}:%"),
            )
        )
        or 0
    )


def _reminder_notifications(db, meeting_id: int) -> list[Notification]:
    return list(
        db.scalars(
            select(Notification).where(
                Notification.entity_type == "cm_meeting",
                Notification.entity_id == meeting_id,
                Notification.body.like(f"%meeting_reminder:{meeting_id}:%"),
            )
        ).all()
    )


def _meeting(meeting_id: int) -> CaseManagerMeeting:
    db = SessionLocal()
    try:
        meeting = db.get(CaseManagerMeeting, meeting_id)
        assert meeting is not None
        return meeting
    finally:
        db.close()


def test_meeting_62_minutes_out_gets_one_reminder_per_participant(monkeypatch):
    from datetime import datetime

    from app.core.timezone import IST

    # Freeze clock so 11:30 is exactly 62 min ahead (batch window 55–70, create hook skips >=60).
    fixed_now = datetime(2026, 9, 4, 10, 28, 0, tzinfo=IST)

    def _fixed_now():
        return fixed_now

    monkeypatch.setattr("app.core.timezone.now_ist", _fixed_now)
    monkeypatch.setattr("app.services.availability_service.now_ist", _fixed_now)
    monkeypatch.setattr("app.services.cm_meeting_service.now_ist", _fixed_now)
    monkeypatch.setattr("app.api.v1.meetings.now_ist", _fixed_now)

    create = client.post(
        "/api/v1/meetings",
        headers=_headers("superadmin@demo.com"),
        json={
            "case_id": _bookable_case_id(),
            "invite_client": False,
            "scheduled_date": "2026-09-04",
            "scheduled_time": "11:30:00",
            "duration_minutes": 30,
            "meeting_type": "PARENT_MEETING",
        },
    )
    assert create.status_code == 201, create.text
    meeting_id = create.json()["id"]

    db = SessionLocal()
    try:
        meeting = db.get(CaseManagerMeeting, meeting_id)
        assert meeting is not None
        participants = meeting_participant_user_ids(meeting)
        stats = send_due_meeting_reminders(db, fixed_now)
        db.commit()
        db.refresh(meeting)
        second = send_due_meeting_reminders(db, fixed_now)
        db.commit()

        reminders = _reminder_notifications(db, meeting_id)
        assert stats["sent"] == 1
        assert second["sent"] == 0
        assert len(reminders) == len(participants)
        assert meeting.reminder_sent_at is not None
        assert all(note.body.startswith("[meeting_reminder:") for note in reminders)
    finally:
        db.close()


def test_cancelled_meeting_gets_no_reminder():
    create = client.post(
        "/api/v1/meetings",
        headers=_headers("superadmin@demo.com"),
        json={
            "case_id": _bookable_case_id(),
            "scheduled_date": future_meeting_date(30),
            "scheduled_time": "10:00:00",
            "duration_minutes": 30,
            "meeting_type": "PARENT_MEETING",
            "invite_client": False,
        },
    )
    assert create.status_code == 201, create.text
    meeting_id = create.json()["id"]

    cancelled = client.post(
        f"/api/v1/meetings/{meeting_id}/cancel",
        headers=_headers("superadmin@demo.com"),
        json={"reason": "Not needed"},
    )
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status"] == MeetingStatus.CANCELLED.value

    db = SessionLocal()
    try:
        stats = send_due_meeting_reminders(db, now_ist())
        db.commit()
        assert stats["sent"] == 0
        assert _reminder_notification_count(db, meeting_id) == 0
    finally:
        db.close()


def test_meeting_booked_30_minutes_ahead_sends_reminder_at_booking(monkeypatch):
    from datetime import datetime

    from app.core.timezone import IST

    fixed_now = datetime(2026, 9, 4, 10, 30, 0, tzinfo=IST)

    def _fixed_now():
        return fixed_now

    monkeypatch.setattr("app.core.timezone.now_ist", _fixed_now)
    monkeypatch.setattr("app.services.availability_service.now_ist", _fixed_now)
    monkeypatch.setattr("app.services.cm_meeting_service.now_ist", _fixed_now)
    monkeypatch.setattr("app.api.v1.meetings.now_ist", _fixed_now)

    create = client.post(
        "/api/v1/meetings",
        headers=_headers("superadmin@demo.com"),
        json={
            "case_id": _bookable_case_id(),
            "invite_client": False,
            "scheduled_date": "2026-09-04",
            "scheduled_time": "11:00:00",
            "duration_minutes": 30,
            "meeting_type": "PARENT_MEETING",
        },
    )
    assert create.status_code == 201, create.text
    meeting_id = create.json()["id"]

    db = SessionLocal()
    try:
        meeting = db.get(CaseManagerMeeting, meeting_id)
        assert meeting is not None
        participants = meeting_participant_user_ids(meeting)
        reminders = _reminder_notifications(db, meeting_id)
        assert len(reminders) == len(participants)
        assert meeting.reminder_sent_at is not None
    finally:
        db.close()
