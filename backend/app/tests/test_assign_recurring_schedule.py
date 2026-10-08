from __future__ import annotations

import os
from datetime import date, timedelta

from app.services.recurring_expansion import expand_weekday_dates
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.database import engine
from app.main import app
from app.seed.demo_seed import run as seed_run

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


def test_assign_recurring_schedule():
    admin = _login("admin@demo.com")
    therapist = _login("therapist@demo.com")
    th = _headers(therapist)

    cases = client.get("/api/v1/slots/bookable-cases", headers=th).json()
    assert cases
    case_id = cases[0]["case_id"]
    me = client.get("/api/v1/auth/me", headers=th).json()
    therapist_user_id = me["id"]

    start = date(2026, 8, 4)
    end = start + timedelta(days=13)
    resp = client.post(
        "/api/v1/scheduling/assign-recurring",
        headers=_headers(admin),
        json={
            "case_id": case_id,
            "therapist_user_id": therapist_user_id,
            "weekdays": ["mon", "wed"],
            "start_time": "10:00:00",
            "end_time": "11:00:00",
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["booked_slot_count"] >= 1
    assert body["recurrence_group_id"]

    cal = client.get(
        f"/api/v1/scheduling/calendar?from_date={start.isoformat()}&to_date={end.isoformat()}",
        headers=th,
    )
    assert cal.status_code == 200
    booked = [s for s in cal.json()["slots"] if s["status"] == "BOOKED" and s["case_id"] == case_id]
    assert len(booked) >= body["booked_slot_count"]


def test_assign_recurring_schedule_therapist_self():
    """Therapists with slot.book may assign recurring for their own calendar + assigned case."""
    therapist = _login("therapist@demo.com")
    th = _headers(therapist)

    cases = client.get("/api/v1/slots/bookable-cases", headers=th).json()
    assert cases
    case_id = cases[0]["case_id"]
    me = client.get("/api/v1/auth/me", headers=th).json()
    therapist_user_id = me["id"]

    start = date(2026, 8, 4)
    end = start + timedelta(days=13)
    resp = client.post(
        "/api/v1/scheduling/assign-recurring",
        headers=th,
        json={
            "case_id": case_id,
            "therapist_user_id": therapist_user_id,
            "weekdays": ["tue", "thu"],
            "start_time": "11:00:00",
            "end_time": "12:00:00",
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
        },
    )
    assert resp.status_code == 201, resp.text


def test_scheduling_create_and_patch_slot():
    therapist = _login("therapist@demo.com")
    th = _headers(therapist)
    day = date(2026, 9, 1)

    created = client.post(
        "/api/v1/scheduling/slots",
        headers=th,
        json={
            "slot_date": day.isoformat(),
            "start_time": "14:00:00",
            "end_time": "15:00:00",
        },
    )
    assert created.status_code == 201
    slot_id = created.json()["id"]

    patched = client.patch(
        f"/api/v1/scheduling/slots/{slot_id}",
        headers=th,
        json={"start_time": "15:00:00", "end_time": "16:00:00"},
    )
    assert patched.status_code == 200
    assert patched.json()["start_time"] == "15:00"


def _note_titles(token: str, path: str) -> list[str]:
    resp = client.get(path, headers=_headers(token))
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    rows = payload["notifications"] if isinstance(payload, dict) else payload
    return [row["title"] for row in rows]


def test_recurring_books_selected_weekdays_and_batches_notifications():
    """Thursday start + Mon/Wed/Fri for 8 weeks books every in-range day once, and notifies once."""
    therapist = _login("therapist@demo.com")
    parent = _login("parent@demo.com")
    shadow_cm = _login("shadowcm@demo.com")
    case_mgr = _login("casemanager@demo.com")
    th = _headers(therapist)

    cases = client.get("/api/v1/slots/bookable-cases", headers=th).json()
    assert cases
    case_id = cases[0]["case_id"]
    me = client.get("/api/v1/auth/me", headers=th).json()
    therapist_user_id = me["id"]

    start = date(2026, 10, 8)
    end = start + timedelta(days=8 * 7 - 1)
    expected = expand_weekday_dates(start, end, ["mon", "wed", "fri"])

    before = {
        "parent": _note_titles(parent, "/api/v1/parent/notifications"),
        "therapist": _note_titles(therapist, "/api/v1/notifications"),
        "shadow": _note_titles(shadow_cm, "/api/v1/notifications"),
        "cm": _note_titles(case_mgr, "/api/v1/notifications"),
    }

    resp = client.post(
        "/api/v1/scheduling/assign-recurring",
        headers=th,
        json={
            "case_id": case_id,
            "therapist_user_id": therapist_user_id,
            "weekdays": ["mon", "wed", "fri"],
            "start_time": "08:00:00",
            "end_time": "14:30:00",
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["booked_slot_count"] == len(expected)
    assert body["outside_week"] == ["mon", "wed"]
    assert body["skipped"] == []

    cal = client.get(
        f"/api/v1/scheduling/calendar?from_date={start.isoformat()}&to_date={end.isoformat()}",
        headers=th,
    )
    assert cal.status_code == 200
    booked_dates = sorted(
        s["slot_date"]
        for s in cal.json()["slots"]
        if s["status"] == "BOOKED" and s["case_id"] == case_id and s["start_time"].startswith("08:00")
    )
    assert booked_dates == [d.isoformat() for d in expected]
    assert "2026-10-05" not in booked_dates
    assert "2026-10-09" in booked_dates

    after_parent = _note_titles(parent, "/api/v1/parent/notifications")
    after_therapist = _note_titles(therapist, "/api/v1/notifications")
    after_shadow = _note_titles(shadow_cm, "/api/v1/notifications")
    after_cm = _note_titles(case_mgr, "/api/v1/notifications")

    def added(before_rows, after_rows, title):
        return after_rows.count(title) - before_rows.count(title)

    assert added(before["parent"], after_parent, "Recurring sessions scheduled") == 1
    assert added(before["therapist"], after_therapist, "Recurring schedule assigned") == 1
    manager_added = added(before["shadow"], after_shadow, "Recurring schedule booked") + added(
        before["cm"], after_cm, "Recurring schedule booked"
    )
    assert manager_added == 1
    assert added(before["parent"], after_parent, "Session booked") == 0

    again = client.post(
        "/api/v1/scheduling/assign-recurring",
        headers=th,
        json={
            "case_id": case_id,
            "therapist_user_id": therapist_user_id,
            "weekdays": ["mon", "wed", "fri"],
            "start_time": "08:00:00",
            "end_time": "14:30:00",
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
        },
    )
    assert again.status_code == 201, again.text
    assert again.json()["booked_slot_count"] == 0
    assert len(again.json()["skipped"]) == len(expected)
    parent_after_repeat = _note_titles(parent, "/api/v1/parent/notifications")
    assert added(after_parent, parent_after_repeat, "Recurring sessions scheduled") == 1
    assert added(after_parent, parent_after_repeat, "Session booked") == 0


def test_one_off_book_still_notifies_parent_once():
    therapist = _login("therapist@demo.com")
    parent = _login("parent@demo.com")
    th = _headers(therapist)
    cases = client.get("/api/v1/slots/bookable-cases", headers=th).json()
    case_id = cases[0]["case_id"]
    day = date(2027, 1, 4)
    created = client.post(
        "/api/v1/scheduling/slots",
        headers=th,
        json={"slot_date": day.isoformat(), "start_time": "15:00:00", "end_time": "16:00:00"},
    )
    assert created.status_code == 201, created.text
    slot_id = created.json()["id"]
    before = _note_titles(parent, "/api/v1/parent/notifications")
    booked = client.post(
        f"/api/v1/scheduling/slots/{slot_id}/book",
        headers=th,
        json={"case_id": case_id, "notify_client": True},
    )
    assert booked.status_code == 200, booked.text
    after = _note_titles(parent, "/api/v1/parent/notifications")
    assert after.count("Session booked") - before.count("Session booked") == 1

    created_quiet = client.post(
        "/api/v1/scheduling/slots",
        headers=th,
        json={"slot_date": day.isoformat(), "start_time": "16:00:00", "end_time": "17:00:00"},
    )
    assert created_quiet.status_code == 201, created_quiet.text
    quiet = client.post(
        f"/api/v1/scheduling/slots/{created_quiet.json()['id']}/book",
        headers=th,
        json={"case_id": case_id, "notify_client": False},
    )
    assert quiet.status_code == 200, quiet.text
    quiet_notes = _note_titles(parent, "/api/v1/parent/notifications")
    assert quiet_notes.count("Session booked") == after.count("Session booked")
