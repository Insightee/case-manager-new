from __future__ import annotations

import os
from datetime import date, timedelta
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
