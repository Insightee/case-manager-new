from __future__ import annotations

from datetime import date, time, timedelta

import pytest
from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app.main import app
from app.models.session import Session as TherapySession
from app.models.session import SessionMode, SessionStatus
from app.seed.demo_seed import run as seed_run

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    seed_run()


def _login(email: str, password: str = "demo123"):
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200
    return r.json()["access_token"]


def test_calendar_includes_scheduled_sessions_without_slots():
    token = _login("therapist@demo.com")
    headers = {"Authorization": f"Bearer {token}"}
    me = client.get("/api/v1/auth/me", headers=headers).json()
    cases = client.get("/api/v1/cases", headers=headers).json()
    items = cases if isinstance(cases, list) else cases.get("items", [])
    assert items
    case_id = items[0]["id"]
    visit_date = date.today() + timedelta(days=3)
    db = SessionLocal()
    try:
        session = TherapySession(
            case_id=case_id,
            therapist_user_id=me["id"],
            scheduled_date=visit_date,
            start_time=time(10, 0),
            end_time=time(11, 0),
            mode=SessionMode.HOME,
            status=SessionStatus.SCHEDULED,
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        session_id = session.id
    finally:
        db.close()

    cal = client.get(
        f"/api/v1/scheduling/calendar?from_date={visit_date.isoformat()}&to_date={visit_date.isoformat()}",
        headers=headers,
    )
    assert cal.status_code == 200
    sessions = cal.json()["sessions"]
    match = next((s for s in sessions if s.get("session_id") == session_id), None)
    assert match is not None
    assert match["event_type"] == "session"
    assert match["child_name"] or match["case_code"]
