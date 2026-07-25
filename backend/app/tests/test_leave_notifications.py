from __future__ import annotations

import os
from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from app.core.config import settings
from app.core.database import SessionLocal, engine
from app.core.timezone import today_ist
from app.main import app
from app.models.slot import SlotStatus, TherapistSlot
from app.seed.demo_seed import run as seed_run

client = TestClient(app)


def _future_leave_day(offset_days: int) -> date:
    """Self-service leave rejects past dates; keep tests anchored to IST today."""
    d = today_ist() + timedelta(days=offset_days)
    # Default schedule template only materializes Mon–Fri slots.
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


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


def _parent_notifications(token: str) -> list[dict]:
    r = client.get("/api/v1/parent/notifications", headers=_headers(token))
    assert r.status_code == 200
    return r.json()


def test_tentative_notification_on_leave_submit():
    therapist = _login("therapist@demo.com")
    parent = _login("parent@demo.com")
    th = _headers(therapist)

    day = _future_leave_day(14)
    client.post(
        "/api/v1/slots/materialize",
        headers=th,
        json={"from_date": day.isoformat(), "to_date": day.isoformat()},
    )

    leave = client.post(
        "/api/v1/leave",
        headers=th,
        json={
            "service_line": "shadow_support",
            "leave_type": "CASUAL",
            "start_date": day.isoformat(),
            "end_date": day.isoformat(),
            "reason": "Personal",
        },
    )
    assert leave.status_code == 201

    notes = _parent_notifications(parent)
    assert any(n["title"] == "Therapist leave requested" for n in notes)
    tentative = next(n for n in notes if n["title"] == "Therapist leave requested")
    assert "under review" in tentative["body"].lower() or "not cancelled" in tentative["body"].lower()


def test_approve_cancels_slot_and_confirms_parent():
    therapist = _login("therapist@demo.com")
    parent = _login("parent@demo.com")
    hr = _login("hr@demo.com")
    th = _headers(therapist)

    day = _future_leave_day(21)
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
    assert available
    cases = client.get("/api/v1/slots/bookable-cases", headers=th).json()
    slot_id = available[0]["id"]
    case_id = cases[0]["case_id"]

    book = client.post(
        f"/api/v1/slots/{slot_id}/book",
        headers=th,
        json={"case_id": case_id},
    )
    assert book.status_code == 200

    leave = client.post(
        "/api/v1/leave",
        headers=th,
        json={
            "service_line": "shadow_support",
            "leave_type": "ANNUAL",
            "start_date": day.isoformat(),
            "end_date": day.isoformat(),
        },
    )
    assert leave.status_code == 201
    leave_id = leave.json()["id"]

    review = client.patch(
        f"/api/v1/leave/{leave_id}",
        headers=_headers(hr),
        json={"status": "APPROVED"},
    )
    assert review.status_code == 200

    db = SessionLocal()
    try:
        slot = db.get(TherapistSlot, slot_id)
        assert slot.status == SlotStatus.CANCELLED
        assert slot.case_id is None
    finally:
        db.close()

    notes = _parent_notifications(parent)
    leave_notes = [n for n in notes if n.get("entity_id") == leave_id]
    assert any(
        "cancelled" in n["title"].lower() or "on leave" in n["title"].lower() for n in leave_notes
    ), [n["title"] for n in leave_notes]
    body_text = " ".join(n["body"] for n in leave_notes)
    assert day.isoformat() in body_text


def test_reject_keeps_booking_and_notifies_parent():
    therapist = _login("therapist@demo.com")
    parent = _login("parent@demo.com")
    hr = _login("hr@demo.com")
    th = _headers(therapist)

    day = _future_leave_day(28)
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
    cases = client.get("/api/v1/slots/bookable-cases", headers=th).json()
    slot_id = available[0]["id"]
    case_id = cases[0]["case_id"]
    client.post(f"/api/v1/slots/{slot_id}/book", headers=th, json={"case_id": case_id})

    leave = client.post(
        "/api/v1/leave",
        headers=th,
        json={
            "service_line": "shadow_support",
            "leave_type": "SICK",
            "start_date": day.isoformat(),
            "end_date": day.isoformat(),
        },
    )
    leave_id = leave.json()["id"]

    review = client.patch(
        f"/api/v1/leave/{leave_id}",
        headers=_headers(hr),
        json={"status": "REJECTED", "review_note": "Slot must stay booked for client session"},
    )
    assert review.status_code == 200

    db = SessionLocal()
    try:
        slot = db.get(TherapistSlot, slot_id)
        assert slot.status == SlotStatus.BOOKED
        assert slot.case_id == case_id
    finally:
        db.close()

    notes = _parent_notifications(parent)
    assert any(n["title"] == "Leave request not approved" for n in notes)


def _staff_notifications(token: str) -> list[dict]:
    r = client.get("/api/v1/notifications", headers=_headers(token))
    assert r.status_code == 200
    return r.json().get("notifications", r.json())


def test_cm_notified_on_leave_submit_hr_not_notified():
    therapist = _login("therapist@demo.com")
    hr = _login("hr@demo.com")
    cm = _login("shadowcm@demo.com")
    day = _future_leave_day(35)
    leave = client.post(
        "/api/v1/leave",
        headers=_headers(therapist),
        json={
            "service_line": "shadow_support",
            "leave_type": "ANNUAL",
            "start_date": day.isoformat(),
            "end_date": day.isoformat(),
            "reason": "Vacation",
        },
    )
    assert leave.status_code == 201
    leave_id = leave.json()["id"]

    cm_notes = _staff_notifications(cm)
    assert any(
        n.get("entity_id") == leave_id and "pending" in n["title"].lower()
        for n in cm_notes
    )

    hr_notes = _staff_notifications(hr)
    assert not any(n.get("entity_id") == leave_id for n in hr_notes)


def test_therapist_notified_on_reject_with_note():
    therapist = _login("therapist@demo.com")
    hr = _login("hr@demo.com")
    th = _headers(therapist)
    day = _future_leave_day(42)

    leave = client.post(
        "/api/v1/leave",
        headers=th,
        json={
            "service_line": "shadow_support",
            "leave_type": "CASUAL",
            "start_date": day.isoformat(),
            "end_date": day.isoformat(),
        },
    )
    assert leave.status_code == 201
    leave_id = leave.json()["id"]

    review = client.patch(
        f"/api/v1/leave/{leave_id}",
        headers=_headers(hr),
        json={"status": "REJECTED", "review_note": "Coverage required that week"},
    )
    assert review.status_code == 200

    notes = _staff_notifications(therapist)
    reject_notes = [
        n for n in notes
        if n.get("entity_id") == leave_id and "not approved" in n["title"].lower()
    ]
    assert len(reject_notes) >= 1
    assert "Coverage required" in reject_notes[0]["body"]


def test_case_scoped_leave_only_affects_selected_case():
    """Shadow-only leave must not mention or cancel homecare sessions."""
    therapist = _login("therapist@demo.com")
    parent = _login("parent@demo.com")
    hr = _login("hr@demo.com")
    th = _headers(therapist)

    cases = client.get("/api/v1/slots/bookable-cases", headers=th).json()
    assert len(cases) >= 2, "Seed therapist needs shadow + homecare cases"
    shadow = next(c for c in cases if c.get("product_module") == "shadow_support")
    homecare = next(c for c in cases if c["case_id"] != shadow["case_id"])

    day = _future_leave_day(49)
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
    assert len(available) >= 2, "Need at least two open slots for booking test"

    homecare_slot_id = available[0]["id"]
    shadow_slot_id = available[1]["id"]
    assert (
        client.post(
            f"/api/v1/slots/{homecare_slot_id}/book",
            headers=th,
            json={"case_id": homecare["case_id"]},
        ).status_code
        == 200
    )
    assert (
        client.post(
            f"/api/v1/slots/{shadow_slot_id}/book",
            headers=th,
            json={"case_id": shadow["case_id"]},
        ).status_code
        == 200
    )

    leave = client.post(
        "/api/v1/leave",
        headers=th,
        json={
            "service_line": "shadow_support",
            "leave_type": "ANNUAL",
            "start_date": day.isoformat(),
            "end_date": day.isoformat(),
            "case_ids": [shadow["case_id"]],
        },
    )
    assert leave.status_code == 201
    leave_id = leave.json()["id"]

    notes = _parent_notifications(parent)
    tentative = [n for n in notes if n.get("entity_id") == leave_id and n["title"] == "Therapist leave requested"]
    assert len(tentative) == 1
    assert shadow["case_code"] in tentative[0]["body"]
    assert homecare["case_code"] not in tentative[0]["body"]

    review = client.patch(
        f"/api/v1/leave/{leave_id}",
        headers=_headers(hr),
        json={"status": "APPROVED"},
    )
    assert review.status_code == 200

    db = SessionLocal()
    try:
        homecare_slot = db.get(TherapistSlot, homecare_slot_id)
        shadow_slot = db.get(TherapistSlot, shadow_slot_id)
        assert homecare_slot.status == SlotStatus.BOOKED
        assert homecare_slot.case_id == homecare["case_id"]
        assert shadow_slot.status == SlotStatus.CANCELLED
    finally:
        db.close()

    notes = _parent_notifications(parent)
    leave_notes = [n for n in notes if n.get("entity_id") == leave_id]
    bodies = " ".join(n["body"] for n in leave_notes)
    assert homecare["case_code"] not in bodies
    assert shadow["case_code"] in bodies


def test_leave_summary_and_report():
    therapist = _login("therapist@demo.com")
    hr = _login("hr@demo.com")
    year = today_ist().year

    summary = client.get(
        f"/api/v1/leave/summary?year={year}",
        headers=_headers(therapist),
    )
    assert summary.status_code == 200
    body = summary.json()
    assert "approved_days" in body
    assert "entries" in body

    report = client.get(
        f"/api/v1/leave/report?year={year}&granularity=monthly",
        headers=_headers(hr),
    )
    assert report.status_code == 200
    assert "rows" in report.json()

    csv_res = client.get(
        f"/api/v1/leave/report?year={year}&granularity=yearly&format=csv",
        headers=_headers(hr),
    )
    assert csv_res.status_code == 200
    assert "therapist_name" in csv_res.text

    denied = client.get(
        f"/api/v1/leave/report?year={year}",
        headers=_headers(therapist),
    )
    assert denied.status_code == 403
