from __future__ import annotations

import os
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import settings
from app.core.database import SessionLocal, engine
from app.main import app
from app.models.leave import LeaveBillingCategory, LeaveStatus, LeaveType, TherapistLeave
from app.models.therapist_profile import TherapistProfile
from app.models.user import User
from app.services import leave_policy_service as policy
from app.seed.demo_seed import run as seed_run

client = TestClient(app)


def _reset_sqlite_db() -> None:
    url = settings.database_url
    if not url.startswith("sqlite"):
        return
    rel = url.replace("sqlite:///", "")
    db_path = Path(rel) if os.path.isabs(rel) else Path(__file__).resolve().parents[2] / rel.lstrip("./")
    engine.dispose()
    for suffix in ("", "-wal", "-shm"):
        p = Path(f"{db_path}{suffix}")
        if p.exists():
            p.unlink()


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


def _ensure_therapist_profile(db, user_id: int) -> TherapistProfile:
    profile = db.scalars(select(TherapistProfile).where(TherapistProfile.user_id == user_id)).first()
    if not profile:
        profile = TherapistProfile(user_id=user_id)
        db.add(profile)
    profile.employment_start_date = date(2020, 1, 1)
    profile.leave_balance_year = 2026
    profile.leave_paid_days_backfill = 0
    profile.leave_carry_forward_days_backfill = 0
    db.commit()
    return profile


def test_balance_includes_backfill():
    db = SessionLocal()
    try:
        user = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
        assert user
        profile = _ensure_therapist_profile(db, user.id)
        before = policy.get_leave_balance(db, user, year=2026)
        profile.leave_paid_days_backfill = 2
        profile.leave_carry_forward_days_backfill = 0
        db.add(
            TherapistLeave(
                therapist_user_id=user.id,
                leave_type=LeaveType.ANNUAL,
                service_line="shadow_support",
                billing_category=LeaveBillingCategory.PAID,
                start_date=date(2026, 11, 1),
                end_date=date(2026, 11, 3),
                status=LeaveStatus.APPROVED,
            )
        )
        db.commit()

        bal = policy.get_leave_balance(db, user, year=2026)
        assert bal["computed_paid_used"] == before["computed_paid_used"] + 3
        assert bal["backfill_paid_used"] == 2
        assert bal["paid_used_effective"] == bal["computed_paid_used"] + 2
        assert bal["paid_remaining"] == bal["entitlement_paid"] - bal["paid_used_effective"]
    finally:
        db.close()


def test_backfill_ignored_wrong_year():
    db = SessionLocal()
    try:
        user = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
        profile = _ensure_therapist_profile(db, user.id)
        profile.leave_balance_year = 2025
        db.commit()
        bal = policy.get_leave_balance(db, user, year=2026)
        assert bal["backfill_paid_used"] == 0
    finally:
        db.close()


def test_non_shadow_suggest_unpaid():
    db = SessionLocal()
    try:
        user = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
        _ensure_therapist_profile(db, user.id)
        sug = policy.suggest_leave_split(
            db,
            user,
            start_date=date(2026, 6, 1),
            end_date=date(2026, 6, 2),
            service_line="homecare",
        )
        assert sug.paid_days == 0
        assert sug.unpaid_days == 2
    finally:
        db.close()


def test_leave_balance_api():
    therapist = _login("therapist@demo.com")
    db = SessionLocal()
    try:
        user = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
        _ensure_therapist_profile(db, user.id)
    finally:
        db.close()
    r = client.get("/api/v1/leave/balance?year=2026", headers=_headers(therapist))
    assert r.status_code == 200
    data = r.json()
    assert "paid_remaining" in data
    assert "entitlement_paid" in data


def test_hr_leave_backfill_requires_note():
    hr = _login("hr@demo.com")
    db = SessionLocal()
    try:
        user = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
        therapist_id = user.id
    finally:
        db.close()

    r = client.patch(
        f"/api/v1/hr/therapists/{therapist_id}/leave-backfill",
        headers=_headers(hr),
        json={
            "year": 2026,
            "leave_paid_days_backfill": 1,
            "leave_carry_forward_days_backfill": 0,
        },
    )
    assert r.status_code == 400

    r2 = client.patch(
        f"/api/v1/hr/therapists/{therapist_id}/leave-backfill",
        headers=_headers(hr),
        json={
            "year": 2026,
            "leave_paid_days_backfill": 1,
            "leave_carry_forward_days_backfill": 0,
            "leave_backfill_note": "Offline leave in March",
            "employment_start_date": "2020-01-01",
        },
    )
    assert r2.status_code == 200
    assert r2.json()["leave_balance"]["backfill_paid_used"] == 1


def test_create_leave_requires_service_line_and_profile():
    therapist = _login("therapist@demo.com")
    db = SessionLocal()
    try:
        user = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
        _ensure_therapist_profile(db, user.id)
    finally:
        db.close()

    r = client.post(
        "/api/v1/leave",
        headers=_headers(therapist),
        json={
            "service_line": "shadow_support",
            "billing_category": "UNPAID",
            "start_date": "2026-08-01",
            "end_date": "2026-08-01",
            "reason": "Test",
        },
    )
    assert r.status_code == 201
    assert r.json()["service_line"] == "shadow_support"
