from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.scheduling_defaults import default_open_windows, default_weekday_indices
from app.main import app
from app.models.user import User
from app.services import availability_service, availability_sync
from app.services.slot_calendar_service import get_or_create_template
from app.tests.conftest import login_headers
from app.core.database import SessionLocal

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


def test_weekends_disabled_by_default():
    assert settings.scheduling_weekends_enabled is False
    assert 5 not in default_open_windows()
    assert 6 not in default_open_windows()
    assert default_weekday_indices() == [0, 1, 2, 3, 4]


def test_weekends_enabled_when_configured(monkeypatch):
    monkeypatch.setattr(settings, "scheduling_weekends_enabled", True)
    assert 5 in default_open_windows()
    assert 6 in default_open_windows()
    assert default_weekday_indices() == list(range(7))


def test_save_availability_syncs_template():
    headers = login_headers(client, "therapist@demo.com")
    user = _get_user("therapist@demo.com")
    saturday = _next_weekday(date.today(), 5)

    res = client.put(
        f"/api/v1/users/{user.id}/availability",
        headers=headers,
        json={
            "rules": [
                {
                    "weekday": saturday.weekday(),
                    "start_time": "09:00",
                    "end_time": "13:00",
                    "slot_granularity_minutes": 30,
                }
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
    assert res.status_code == 200, res.text

    db = SessionLocal()
    try:
        template = get_or_create_template(db, user.id).get_config()
        sat = template["days"]["sat"]
        assert sat["enabled"] is True
        assert sat["start"] == "09:00"
        assert sat["end"] == "13:00"
    finally:
        db.close()


def test_template_patch_syncs_staff_rules():
    headers = login_headers(client, "therapist@demo.com")
    user = _get_user("therapist@demo.com")
    sunday = _next_weekday(date.today(), 6)

    template_res = client.get("/api/v1/slots/template", headers=headers)
    assert template_res.status_code == 200, template_res.text
    config = template_res.json()["config"]
    config["days"]["sun"] = {"enabled": True, "start": "10:00", "end": "14:00"}

    patch_res = client.patch(
        "/api/v1/slots/template",
        headers=headers,
        json={"config": config},
    )
    assert patch_res.status_code == 200, patch_res.text

    availability_res = client.get(f"/api/v1/users/{user.id}/availability", headers=headers)
    assert availability_res.status_code == 200, availability_res.text
    rules = availability_res.json()["rules"]
    sunday_rules = [row for row in rules if row["weekday"] == sunday.weekday()]
    assert sunday_rules
    assert sunday_rules[0]["start_time"] == "10:00"
    assert sunday_rules[0]["end_time"] == "14:00"


def test_materialize_uses_staff_rules_when_policy_exists():
    headers = login_headers(client, "therapist@demo.com")
    user = _get_user("therapist@demo.com")
    target = _next_weekday(date.today(), 2)

    save_res = client.put(
        f"/api/v1/users/{user.id}/availability",
        headers=headers,
        json={
            "rules": [
                {
                    "weekday": target.weekday(),
                    "start_time": "11:00",
                    "end_time": "12:00",
                    "slot_granularity_minutes": 60,
                }
            ],
            "exceptions": [],
            "booking_policy": {
                "min_notice_minutes": 0,
                "max_days_ahead": 60,
                "buffer_minutes": 0,
                "allowed_durations": [60],
            },
        },
    )
    assert save_res.status_code == 200, save_res.text

    materialize_res = client.post(
        "/api/v1/slots/materialize",
        headers=headers,
        json={"from_date": target.isoformat(), "to_date": target.isoformat()},
    )
    assert materialize_res.status_code == 200, materialize_res.text

    slots_res = client.get(
        "/api/v1/slots",
        headers=headers,
        params={"from_date": target.isoformat(), "to_date": target.isoformat()},
    )
    assert slots_res.status_code == 200, slots_res.text
    starts = {row["start_time"][:5] for row in slots_res.json()}
    assert starts == {"11:00"}


def test_template_days_to_rules_and_back():
    days = availability_sync.rules_to_template_days([])
    assert days["mon"]["enabled"] is False

    rules = availability_sync.template_days_to_rules(
        {
            "mon": {"enabled": True, "start": "09:00", "end": "17:00"},
            "sat": {"enabled": False, "start": "09:00", "end": "17:00"},
        }
    )
    assert len(rules) == 1
    assert rules[0]["weekday"] == 0
    assert rules[0]["start_time"] == "09:00"


def test_slot_start_allowed_respects_staff_policy():
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == "therapist@demo.com").one()
        target = _next_weekday(date.today(), 3)
        availability_service.save_user_availability(
            db,
            user.id,
            {
                "rules": [
                    {
                        "weekday": target.weekday(),
                        "start_time": "10:00",
                        "end_time": "11:00",
                        "slot_granularity_minutes": 30,
                    }
                ],
                "exceptions": [],
                "booking_policy": {
                    "min_notice_minutes": 0,
                    "max_days_ahead": 60,
                    "buffer_minutes": 0,
                    "allowed_durations": [30],
                },
            },
        )
        db.commit()
        from datetime import time

        assert availability_service.slot_start_allowed(db, user.id, target, time(10, 0), 30)
        assert not availability_service.slot_start_allowed(db, user.id, target, time(10, 31), 30)
    finally:
        db.close()
