from __future__ import annotations

import os
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.database import SessionLocal, engine
from app.main import app
from app.models.slot import SlotStatus, TherapistSlot
from app.seed.demo_seed import run as seed_run
from app.services import leave_migration_service as migration

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


def test_migration_info_endpoint():
    therapist = _login("therapist@demo.com")
    r = client.get("/api/v1/leave/migration-info", headers=_headers(therapist))
    assert r.status_code == 200
    data = r.json()
    assert "window_active" in data
    assert data["window_end"] == "2026-06-30"
    assert data["reentry_start"] == "2026-06-01"


def test_therapist_can_submit_june_retroactive_leave():
    if not migration.is_migration_window_active():
        pytest.skip("Migration window closed")
    therapist = _login("therapist@demo.com")
    r = client.post(
        "/api/v1/leave",
        headers=_headers(therapist),
        json={
            "service_line": "shadow_support",
            "start_date": "2026-06-03",
            "end_date": "2026-06-03",
            "reason": "Migration re-entry",
        },
    )
    assert r.status_code == 201
    data = r.json()
    assert data["is_retroactive"] is True
    assert data["is_migration_reentry"] is True


def test_retroactive_approve_skips_slot_cancellation():
    if not migration.is_migration_window_active():
        pytest.skip("Migration window closed")
    therapist = _login("therapist@demo.com")
    hr = _login("hr@demo.com")
    th = _headers(therapist)

    day = date(2026, 6, 10)
    client.post(
        "/api/v1/slots/materialize",
        headers=th,
        json={"from_date": day.isoformat(), "to_date": day.isoformat()},
    )
    cal = client.get(
        f"/api/v1/slots/calendar?from_date={day.isoformat()}&to_date={day.isoformat()}",
        headers=th,
    )
    available = [s for s in cal.json()["slots"] if s["status"] == "AVAILABLE"]
    if not available:
        pytest.skip("No slots to book for retro test day")
    cases = client.get("/api/v1/slots/bookable-cases", headers=th).json()
    slot_id = available[0]["id"]
    book = client.post(
        f"/api/v1/slots/{slot_id}/book",
        headers=th,
        json={"case_id": cases[0]["case_id"]},
    )
    assert book.status_code == 200

    leave = client.post(
        "/api/v1/leave",
        headers=th,
        json={
            "service_line": "shadow_support",
            "start_date": day.isoformat(),
            "end_date": day.isoformat(),
        },
    )
    assert leave.status_code == 201
    leave_id = leave.json()["id"]

    approve = client.patch(
        f"/api/v1/leave/{leave_id}",
        headers=_headers(hr),
        json={"status": "APPROVED"},
    )
    assert approve.status_code == 200

    db = SessionLocal()
    try:
        slot = db.get(TherapistSlot, slot_id)
        assert slot is not None
        assert slot.status == SlotStatus.BOOKED
    finally:
        db.close()


def test_retroactive_submit_skips_parent_notification():
    if not migration.is_migration_window_active():
        pytest.skip("Migration window closed")
    therapist = _login("therapist@demo.com")
    parent = _login("parent@demo.com")
    th = _headers(therapist)

    before = client.get("/api/v1/parent/notifications", headers=_headers(parent)).json()
    before_titles = {n["title"] for n in before}

    r = client.post(
        "/api/v1/leave",
        headers=th,
        json={
            "service_line": "shadow_support",
            "start_date": "2026-06-04",
            "end_date": "2026-06-04",
        },
    )
    assert r.status_code == 201

    after = client.get("/api/v1/parent/notifications", headers=_headers(parent)).json()
    new_notes = [n for n in after if n["title"] not in before_titles]
    assert not any(n["title"] == "Therapist leave requested" for n in new_notes)
