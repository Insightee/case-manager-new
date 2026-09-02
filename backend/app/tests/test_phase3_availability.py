from __future__ import annotations

from datetime import date, timedelta
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app.main import app
from app.models.user import User
from app.services import availability_service
from app.services.calendar_ics import meeting_ics_attachment
from app.tests.conftest import login_headers

client = TestClient(app)


def _next_weekday(start: date, weekday: int) -> date:
    days = (weekday - start.weekday() + 7) % 7
    if days == 0:
        days = 7
    return start + timedelta(days=days)


def _get_user(email: str) -> User:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).one()
        db.expunge(user)
        return user
    finally:
        db.close()


def _save_availability(headers: dict[str, str], user_id: int, payload: dict[str, object]) -> None:
    res = client.put(f"/api/v1/users/{user_id}/availability", headers=headers, json=payload)
    assert res.status_code == 200, res.text


def test_ninety_minutes_cannot_start_in_final_hour_of_window():
    headers = login_headers(client, "superadmin@demo.com")
    user = _get_user("superadmin@demo.com")
    target = _next_weekday(date.today(), 0)

    res = client.get(
        "/api/v1/calendar/availability",
        headers=headers,
        params={
            "user_ids": str(user.id),
            "date_from": target.isoformat(),
            "date_to": target.isoformat(),
            "duration_minutes": 90,
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert all(slot["time"] != "18:30" for slot in body["slots"])


def test_min_notice_and_max_days_ahead_block_booking():
    headers = login_headers(client, "superadmin@demo.com")
    user = _get_user("superadmin@demo.com")
    target = _next_weekday(date.today(), 0)

    _save_availability(
        headers,
        user.id,
        {
            "rules": [],
            "exceptions": [],
            "booking_policy": {
                "min_notice_minutes": 3000,
                "max_days_ahead": 1,
                "buffer_minutes": 0,
                "allowed_durations": [30, 45, 60, 90],
            },
        },
    )

    res = client.get(
        "/api/v1/calendar/availability",
        headers=headers,
        params={
            "user_ids": str(user.id),
            "date_from": target.isoformat(),
            "date_to": target.isoformat(),
            "duration_minutes": 30,
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["slots"] == []
    assert body["freebusy_stale"] is False


def test_configured_weekday_without_rule_is_closed():
    headers = login_headers(client, "casemanager@demo.com")
    user = _get_user("casemanager@demo.com")
    tuesday = _next_weekday(date.today(), 1)
    monday = tuesday - timedelta(days=1)

    _save_availability(
        headers,
        user.id,
        {
            "rules": [
                {"weekday": tuesday.weekday(), "start_time": "14:00", "end_time": "16:00", "slot_granularity_minutes": 30},
            ],
            "exceptions": [],
            "booking_policy": {
                "min_notice_minutes": 120,
                "max_days_ahead": 60,
                "buffer_minutes": 0,
                "allowed_durations": [30, 45, 60, 90],
            },
        },
    )

    monday_res = client.get(
        "/api/v1/calendar/availability",
        headers=headers,
        params={
            "user_ids": str(user.id),
            "date_from": monday.isoformat(),
            "date_to": monday.isoformat(),
            "duration_minutes": 30,
        },
    )
    assert monday_res.status_code == 200, monday_res.text
    assert monday_res.json()["slots"] == []

    tuesday_res = client.get(
        "/api/v1/calendar/availability",
        headers=headers,
        params={
            "user_ids": str(user.id),
            "date_from": tuesday.isoformat(),
            "date_to": tuesday.isoformat(),
            "duration_minutes": 30,
        },
    )
    assert tuesday_res.status_code == 200, tuesday_res.text
    tuesday_times = {slot["time"] for slot in tuesday_res.json()["slots"]}
    assert tuesday_times == {"14:00", "14:30", "15:00", "15:30"}


def test_closed_exception_removes_the_day():
    headers = login_headers(client, "superadmin@demo.com")
    user = _get_user("superadmin@demo.com")
    target = _next_weekday(date.today(), 0)

    _save_availability(
        headers,
        user.id,
        {
            "rules": [
                {"weekday": target.weekday(), "start_time": "10:00", "end_time": "19:00", "slot_granularity_minutes": 30},
            ],
            "exceptions": [
                {"date": target.isoformat(), "type": "CLOSED", "start_time": None, "end_time": None, "reason": "Field visit"},
            ],
            "booking_policy": {
                "min_notice_minutes": 120,
                "max_days_ahead": 60,
                "buffer_minutes": 0,
                "allowed_durations": [30, 45, 60, 90],
            },
        },
    )

    res = client.get(
        "/api/v1/calendar/availability",
        headers=headers,
        params={
            "user_ids": str(user.id),
            "date_from": target.isoformat(),
            "date_to": target.isoformat(),
            "duration_minutes": 30,
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["slots"] == []


def test_two_attendees_intersection_and_google_fail_open(monkeypatch):
    headers = login_headers(client, "superadmin@demo.com")
    superadmin = _get_user("superadmin@demo.com")
    therapist = _get_user("therapist@demo.com")
    target = _next_weekday(date.today(), 0)

    _save_availability(
        headers,
        superadmin.id,
        {
            "rules": [
                {"weekday": target.weekday(), "start_time": "10:00", "end_time": "12:00", "slot_granularity_minutes": 30},
            ],
            "exceptions": [],
            "booking_policy": {
                "min_notice_minutes": 120,
                "max_days_ahead": 60,
                "buffer_minutes": 0,
                "allowed_durations": [30, 45, 60, 90],
            },
        },
    )
    _save_availability(
        headers,
        therapist.id,
        {
            "rules": [
                {"weekday": target.weekday(), "start_time": "11:00", "end_time": "13:00", "slot_granularity_minutes": 30},
            ],
            "exceptions": [],
            "booking_policy": {
                "min_notice_minutes": 120,
                "max_days_ahead": 60,
                "buffer_minutes": 0,
                "allowed_durations": [30, 45, 60, 90],
            },
        },
    )

    monkeypatch.setattr(
        availability_service,
        "busy_intervals",
        lambda *args, **kwargs: {superadmin.id: [], therapist.id: []},
    )
    monkeypatch.setattr(
        availability_service.settings,
        "google_calendar_freebusy_enabled",
        True,
    )
    monkeypatch.setattr(
        availability_service,
        "_google_batch_freebusy",
        lambda *args, **kwargs: ({superadmin.id: [], therapist.id: []}, {}, False),
    )
    db = SessionLocal()
    try:
        body = availability_service.free_slots(db, [superadmin.id, therapist.id], target, target, 30, superadmin)
    finally:
        db.close()
    assert body["slots"]
    assert all(slot["time"] in {"11:00", "11:30"} for slot in body["slots"])

    monkeypatch.setattr(
        availability_service,
        "_google_batch_freebusy",
        lambda *args, **kwargs: ({superadmin.id: [], therapist.id: []}, {superadmin.id: "Google unreachable", therapist.id: "Google unreachable"}, True),
    )
    db = SessionLocal()
    try:
        direct = availability_service.free_slots(
            db,
            [superadmin.id, therapist.id],
            target,
            target,
            30,
            superadmin,
        )
    finally:
        db.close()
    assert direct["freebusy_stale"] is True
    assert direct["freebusy_reasons"][superadmin.id] == "Google unreachable"


def test_busy_intervals_uses_two_queries():
    class _Rows:
        def all(self):
            return []

    class _Db:
        def __init__(self):
            self.calls = 0

        def scalars(self, *_args, **_kwargs):
            self.calls += 1
            return _Rows()

    db = _Db()
    result = availability_service.busy_intervals(db, [1, 2], date(2026, 8, 31), date(2026, 8, 31))
    assert db.calls == 2
    assert result == {}


def test_ics_uid_sequence_and_cancel_method():
    meeting = SimpleNamespace(
        id=42,
        series_id="series-abc",
        title="CM Review",
        meeting_type=SimpleNamespace(value="PARENT_MEETING"),
        scheduled_date=date(2026, 8, 31),
        scheduled_time=None,
        duration_minutes=30,
        meeting_url="https://meet.example.com/abc",
        case_id=7,
        cancel_reason="Parent conflict",
    )
    request_attachment = meeting_ics_attachment(meeting, method="REQUEST", sequence=2)
    cancel_attachment = meeting_ics_attachment(meeting, method="CANCEL", sequence=3, status="CANCELLED")

    assert request_attachment["content_type"] == "text/calendar"
    assert "UID:series-abc" in request_attachment["content"]
    assert "SEQUENCE:2" in request_attachment["content"]
    assert "METHOD:REQUEST" in request_attachment["content"]
    assert "METHOD:CANCEL" in cancel_attachment["content"]
    assert "SEQUENCE:3" in cancel_attachment["content"]
    assert "STATUS:CANCELLED" in cancel_attachment["content"]

