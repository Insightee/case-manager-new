"""Staff attendance and staff leave API."""

from __future__ import annotations

import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.database import SessionLocal, engine
from app.core.timezone import IST, today_ist
from app.main import app
from app.models.leave import LeaveStatus
from app.models.staff_attendance import StaffAttendance, StaffAttendanceEntryType, StaffAttendanceStatus
from app.seed.demo_seed import run as seed_run
from app.services.staff_attendance_service import auto_close_open_attendance_at_midnight

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
    r = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "demo123", "portal": "staff"},
    )
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_therapist_cannot_use_staff_attendance():
    r = client.post(
        "/api/v1/auth/login",
        json={"email": "therapist@demo.com", "password": "demo123", "portal": "therapist"},
    )
    assert r.status_code == 200
    token = r.json()["access_token"]
    r = client.get("/api/v1/staff-attendance/me/today", headers=_headers(token))
    assert r.status_code == 403


def _clock_in_payload(*, work_mode: str = "OFFICE", lat: float | None = None, lon: float | None = None) -> dict:
    lat = settings.staff_office_latitude if lat is None else lat
    lon = settings.staff_office_longitude if lon is None else lon
    return {
        "work_mode": work_mode,
        "latitude": lat,
        "longitude": lon,
        "place_label": "Test location",
    }


def test_hr_clock_in_save_and_clock_out():
    token = _login("hr@demo.com")
    r = client.post(
        "/api/v1/staff-attendance/clock-in",
        headers=_headers(token),
        json=_clock_in_payload(),
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "IN_PROGRESS"
    assert body["work_mode"] == "OFFICE"
    assert body["clock_in_latitude"] == settings.staff_office_latitude

    r = client.put(
        "/api/v1/staff-attendance/work-summary",
        headers=_headers(token),
        json={"work_summary": "HR ops and people admin"},
    )
    assert r.status_code == 200

    r = client.post(
        "/api/v1/staff-attendance/pause",
        headers=_headers(token),
    )
    assert r.status_code == 403

    r = client.post(
        "/api/v1/staff-attendance/clock-out",
        headers=_headers(token),
        json={"work_summary": "HR ops and people admin"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "COMPLETED"

    r = client.post(
        "/api/v1/staff-attendance/clock-in",
        headers=_headers(token),
        json=_clock_in_payload(),
    )
    assert r.status_code == 400
    assert "finished" in r.json()["detail"].lower()


def test_office_clock_in_outside_geofence():
    token = _login("superadmin@demo.com")
    r = client.post(
        "/api/v1/staff-attendance/clock-in",
        headers=_headers(token),
        json=_clock_in_payload(lat=12.0, lon=77.0),
    )
    assert r.status_code == 400
    assert "office" in r.json()["detail"].lower()


def test_forgot_log_disabled_for_staff():
    token = _login("hr@demo.com")
    leave_date = today_ist()
    start = datetime.combine(leave_date, datetime.min.time().replace(hour=9), tzinfo=IST).astimezone(timezone.utc)
    end = datetime.combine(leave_date, datetime.min.time().replace(hour=18), tzinfo=IST).astimezone(timezone.utc)
    r = client.post(
        "/api/v1/staff-attendance/forgot",
        headers=_headers(token),
        json={
            "work_date": leave_date.isoformat(),
            "start_at": start.isoformat(),
            "end_at": end.isoformat(),
            "work_summary": "Catch up work",
            "reason": "Missed clock in",
        },
    )
    assert r.status_code == 403


def test_super_admin_can_list_staff_attendance():
    hr = _login("hr@demo.com")
    hr_user = client.get("/api/v1/auth/me", headers=_headers(hr)).json()
    admin = _login("superadmin@demo.com")
    r = client.get(
        f"/api/v1/staff-attendance/users/{hr_user['id']}",
        headers=_headers(admin),
    )
    assert r.status_code == 200
    assert "items" in r.json()


def test_midnight_auto_close():
    db = SessionLocal()
    try:
        hr = _login("hr@demo.com")
        hr_user = client.get("/api/v1/auth/me", headers=_headers(hr)).json()
        yesterday = today_ist() - timedelta(days=1)
        row = StaffAttendance(
            user_id=hr_user["id"],
            work_date=yesterday,
            entry_type=StaffAttendanceEntryType.LIVE,
            status=StaffAttendanceStatus.IN_PROGRESS,
            is_paused=False,
        )
        db.add(row)
        db.commit()
        db.refresh(row)

        now_ist = datetime.combine(today_ist(), datetime.min.time(), tzinfo=IST)
        closed = auto_close_open_attendance_at_midnight(db, now_ist)
        db.commit()
        assert row.id in closed
        db.refresh(row)
        assert row.status == StaffAttendanceStatus.AUTO_CLOSED
        assert row.auto_closed is True
    finally:
        db.close()
