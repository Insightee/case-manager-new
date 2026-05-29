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


def test_pending_allotment_recurring_shows_on_calendar():
    """Therapist intake cases stay PENDING_ALLOTMENT but still book and display on calendar."""
    therapist = _login("therapist@demo.com")
    th = _headers(therapist)
    me = client.get("/api/v1/auth/me", headers=th).json()
    therapist_user_id = me["id"]

    intake = client.post(
        "/api/v1/therapist/client-intake",
        headers=th,
        json={
            "client_name": "Recurring Parent",
            "child_name": "Calendar Child",
            "client_email": "recurring.cal.child@example.com",
            "product_module": "homecare",
        },
    )
    assert intake.status_code == 201, intake.text
    body = intake.json()
    case_id = body["case_id"]
    # Intake response omits status; case row is PENDING_ALLOTMENT until admin allotment.

    bookable = client.get("/api/v1/slots/bookable-cases", headers=th).json()
    ids = [c["case_id"] for c in bookable]
    assert case_id in ids
    match = next(c for c in bookable if c["case_id"] == case_id)
    assert match.get("pending_allotment") is True

    start = date.today() + timedelta(days=7)
    # Align to next Monday for predictable weekday
    while start.weekday() != 0:
        start += timedelta(days=1)
    end = start + timedelta(days=13)

    client.post(
        "/api/v1/slots/materialize",
        headers=th,
        json={"from_date": start.isoformat(), "to_date": end.isoformat()},
    )

    assigned = client.post(
        "/api/v1/scheduling/assign-recurring",
        headers=th,
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
    assert assigned.status_code == 201, assigned.text
    booked_count = assigned.json()["booked_slot_count"]
    assert booked_count >= 1

    cal = client.get(
        f"/api/v1/scheduling/calendar?from_date={start.isoformat()}&to_date={end.isoformat()}",
        headers=th,
    )
    assert cal.status_code == 200
    booked = [
        s
        for s in cal.json()["slots"]
        if s["status"] == "BOOKED" and s["case_id"] == case_id
    ]
    assert len(booked) >= 1
    sample = booked[0]
    assert sample.get("child_name")
    assert sample.get("case_status") == "PENDING_ALLOTMENT"

    sessions = client.get(
        f"/api/v1/sessions?case_id={case_id}&page_size=50",
        headers=th,
    )
    assert sessions.status_code == 200, sessions.text
    payload = sessions.json()
    rows = payload.get("items", payload) if isinstance(payload, dict) else payload
    assert isinstance(rows, list)
    dated = [r for r in rows if r.get("scheduled_date")]
    assert len(dated) >= 1, "sessions list should expose scheduled_date for hub upcoming filter"
