from __future__ import annotations

import os
from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import settings
from app.core.database import SessionLocal, engine
from app.main import app
from app.models.appointment_reschedule import AppointmentReschedule
from app.models.slot import SlotStatus, TherapistSlot
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


def test_parent_reschedule_creates_history():
    therapist = _login("therapist@demo.com")
    parent = _login("parent@demo.com")
    th, ph = _headers(therapist), _headers(parent)

    start = date(2026, 10, 6)
    end = start + timedelta(days=6)
    client.post(
        "/api/v1/scheduling/template/materialize",
        headers=th,
        params={"from_date": start.isoformat(), "to_date": end.isoformat()},
    )

    cases_r = client.get("/api/v1/parent/cases", headers=ph)
    cases = cases_r.json()
    if not cases:
        pytest.skip("No parent cases in seed")
    case_id = cases[0]["id"]
    therapists = client.get(f"/api/v1/booking/therapists?case_id={case_id}", headers=ph).json()
    tid = therapists[0]["therapist_user_id"]

    cal = client.get(
        f"/api/v1/parent/booking/calendar?case_id={case_id}&therapist_id={tid}"
        f"&from_date={start.isoformat()}&to_date={end.isoformat()}",
        headers=ph,
    )
    available = [s for s in cal.json()["slots"] if s.get("display_status") == "available"]
    if len(available) < 2:
        pytest.skip("Need two bookable slots")
    old_id, new_id = available[0]["id"], available[1]["id"]

    book = client.post(
        "/api/v1/booking/appointments",
        headers=ph,
        json={"case_id": case_id, "slot_id": old_id},
    )
    assert book.status_code in (200, 201), book.text

    resched = client.post(
        f"/api/v1/parent/appointments/{old_id}/reschedule",
        headers=ph,
        json={"new_slot_id": new_id},
    )
    assert resched.status_code == 200, resched.text

    db = SessionLocal()
    try:
        old_slot = db.get(TherapistSlot, old_id)
        assert old_slot.status == SlotStatus.RESCHEDULED
        rows = db.scalars(select(AppointmentReschedule).where(AppointmentReschedule.from_slot_id == old_id)).all()
        assert rows
    finally:
        db.close()
