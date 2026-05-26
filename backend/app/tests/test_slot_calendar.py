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


def test_materialize_multi_window_day():
    """Therapists can define multiple time blocks per day (e.g. break between sessions)."""
    therapist = _login("therapist@demo.com")
    th = _headers(therapist)
    tpl = client.get("/api/v1/slots/template", headers=th)
    assert tpl.status_code == 200
    config = tpl.json()["config"]
    config["slot_duration_minutes"] = 60
    config["days"]["mon"] = {
        "enabled": True,
        "windows": [
            {"start": "09:00", "end": "12:00"},
            {"start": "14:00", "end": "17:00"},
        ],
    }
    patch = client.patch("/api/v1/slots/template", headers=th, json={"config": config})
    assert patch.status_code == 200

    start = date(2026, 7, 6)
    end = date(2026, 7, 6)
    mat = client.post(
        "/api/v1/slots/materialize",
        headers=th,
        json={"from_date": start.isoformat(), "to_date": end.isoformat()},
    )
    assert mat.status_code == 200
    assert mat.json()["created"] >= 5

    cal = client.get(
        f"/api/v1/slots/calendar?from_date={start.isoformat()}&to_date={end.isoformat()}",
        headers=th,
    )
    mon_slots = [s for s in cal.json()["slots"] if s["slot_date"] == start.isoformat()]
    starts = sorted(s["start_time"] for s in mon_slots)
    assert "09:00" in starts
    assert "14:00" in starts
    assert not any(s.startswith("12:") or s.startswith("13:") for s in starts)


def test_materialize_and_book():
    therapist = _login("therapist@demo.com")
    th = _headers(therapist)

    start = date(2026, 6, 2)
    end = start + timedelta(days=6)
    mat = client.post(
        "/api/v1/slots/materialize",
        headers=th,
        json={"from_date": start.isoformat(), "to_date": end.isoformat()},
    )
    assert mat.status_code == 200

    cal = client.get(
        f"/api/v1/slots/calendar?from_date={start.isoformat()}&to_date={end.isoformat()}",
        headers=th,
    )
    assert cal.status_code == 200
    available = [s for s in cal.json()["slots"] if s["status"] == "AVAILABLE"]
    assert available, "Expected available slots (seed or materialize)"

    cases = client.get("/api/v1/slots/bookable-cases", headers=th).json()
    assert cases
    case_id = cases[0]["case_id"]
    slot_id = available[0]["id"]

    book = client.post(
        f"/api/v1/slots/{slot_id}/book",
        headers=th,
        json={"case_id": case_id},
    )
    assert book.status_code == 200
    assert book.json()["status"] == "BOOKED"

    book2 = client.post(
        f"/api/v1/slots/{slot_id}/book",
        headers=th,
        json={"case_id": case_id},
    )
    assert book2.status_code == 400


def test_leave_blocks_parent_availability():
    therapist = _login("therapist@demo.com")
    parent = _login("parent@demo.com")
    th = _headers(therapist)
    ph = _headers(parent)

    day = date(2026, 6, 10)
    client.post(
        "/api/v1/slots/materialize",
        headers=th,
        json={"from_date": day.isoformat(), "to_date": day.isoformat()},
    )
    client.post(
        "/api/v1/leave",
        headers=th,
        json={
            "service_line": "shadow_support",
            "leave_type": "CASUAL",
            "start_date": day.isoformat(),
            "end_date": day.isoformat(),
            "reason": "Day off",
        },
    )

    cases = client.get("/api/v1/parent/cases", headers=ph).json()
    assert cases
    case_id = cases[0]["id"]
    therapists = client.get(f"/api/v1/booking/therapists?case_id={case_id}", headers=ph).json()
    assert therapists
    tid = therapists[0]["therapist_user_id"]

    avail = client.get(
        f"/api/v1/booking/availability?therapist_id={tid}&from_date={day.isoformat()}&to_date={day.isoformat()}",
        headers=ph,
    )
    assert avail.status_code == 200
    assert avail.json() == []
