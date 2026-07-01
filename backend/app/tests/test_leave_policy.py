from __future__ import annotations

import os
from datetime import date, datetime, timezone
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

# Stable accrual anchor — Nov 2025 start earns 6 credits through 18 Jun 2026.
LEAVE_POLICY_AS_OF = date(2026, 6, 18)


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


def _ensure_therapist_profile(
    db,
    user_id: int,
    *,
    employment_start: date = date(2020, 1, 1),
) -> TherapistProfile:
    profile = db.scalars(select(TherapistProfile).where(TherapistProfile.user_id == user_id)).first()
    if not profile:
        profile = TherapistProfile(user_id=user_id)
        db.add(profile)
    profile.employment_start_date = employment_start
    profile.leave_balance_year = 2026
    profile.leave_paid_days_backfill = 0
    profile.leave_carry_forward_days_backfill = 0
    profile.leave_backfill_updated_at = datetime.now(timezone.utc)
    db.commit()
    return profile


def test_monthly_credits_and_consumption():
    db = SessionLocal()
    try:
        user = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
        assert user
        _ensure_therapist_profile(db, user.id, employment_start=date(2025, 11, 1))
        earned = policy.credits_earned_in_year(date(2025, 11, 1), 2026, as_of=LEAVE_POLICY_AS_OF)
        assert earned == 6
        before = policy.get_leave_balance(db, user, year=2026, as_of=LEAVE_POLICY_AS_OF)

        db.add(
            TherapistLeave(
                therapist_user_id=user.id,
                leave_type=LeaveType.ANNUAL,
                service_line="shadow_support",
                billing_category=LeaveBillingCategory.PAID,
                includes_shadow_cases=True,
                start_date=date(2026, 3, 1),
                end_date=date(2026, 3, 7),
                status=LeaveStatus.APPROVED,
            )
        )
        db.commit()

        bal = policy.get_leave_balance(db, user, year=2026, as_of=LEAVE_POLICY_AS_OF)
        assert bal["credits_earned"] == earned
        assert bal["paid_leaves_taken"] == before["paid_leaves_taken"] + 6
        assert bal["unpaid_leaves_taken"] == before["unpaid_leaves_taken"] + 1
        assert bal["leave_credit_pending"] == max(earned - bal["paid_leaves_taken"], 0)
    finally:
        db.close()


def test_credits_zero_without_employment_start():
    db = SessionLocal()
    try:
        user = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
        profile = _ensure_therapist_profile(db, user.id)
        profile.employment_start_date = None
        db.commit()
        bal = policy.get_leave_balance(db, user, year=2026)
        assert bal["credits_earned"] == 0
        assert bal["leave_credit_pending"] == 0
        assert bal["balance_updated"] is False
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
        db.commit()
    finally:
        db.close()
    r = client.get("/api/v1/leave/balance?year=2026", headers=_headers(therapist))
    assert r.status_code == 200
    data = r.json()
    assert "leave_credit_pending" in data
    assert "credits_earned" in data
    assert "paid_leaves_taken" in data
    assert "unpaid_leaves_taken" in data
    assert data["balance_updated"] is True


def test_leave_balance_not_updated_until_hr_save():
    therapist = _login("therapist@demo.com")
    db = SessionLocal()
    try:
        user = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
        profile = _ensure_therapist_profile(db, user.id)
        profile.employment_start_date = None
        profile.leave_backfill_updated_at = None
        db.commit()
    finally:
        db.close()
    r = client.get("/api/v1/leave/balance?year=2026", headers=_headers(therapist))
    assert r.status_code == 200
    assert r.json()["balance_updated"] is False


def test_hr_leave_backfill_requires_note_for_legacy_paid_backfill():
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
            "employment_start_date": "2020-01-01",
        },
    )
    assert r2.status_code == 200
    assert r2.json()["leave_balance"]["employment_start_date"] == "2020-01-01"


def test_create_leave_single_request():
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
            "start_date": "2026-08-01",
            "end_date": "2026-08-01",
            "reason": "Test",
            "consulted_with_parents": True,
        },
    )
    assert r.status_code == 201
    data = r.json()
    assert data["service_line"] == "shadow_support"
    assert data["consulted_with_parents"] is True
    assert data["paid_days"] is not None or data["unpaid_days"] is not None


def test_manual_leave_auto_approved_for_hr():
    hr = _login("hr@demo.com")
    db = SessionLocal()
    try:
        user = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
        therapist_id = user.id
        _ensure_therapist_profile(db, user.id)
        db.commit()
    finally:
        db.close()

    r = client.post(
        "/api/v1/leave/manual",
        headers=_headers(hr),
        json={
            "therapist_user_id": therapist_id,
            "service_line": "shadow_support",
            "start_date": "2026-05-10",
            "end_date": "2026-05-10",
            "reason": "Manual backdated entry",
            "consulted_with_parents": True,
        },
    )
    assert r.status_code == 201
    data = r.json()
    assert data["status"] == "APPROVED"
    assert data["therapist_user_id"] == therapist_id
    assert data["reviewed_by_user_id"] is not None
    assert data["consulted_with_parents"] is True


def test_hr_therapist_cases_endpoint():
    hr = _login("hr@demo.com")
    db = SessionLocal()
    try:
        user = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
        therapist_id = user.id
    finally:
        db.close()

    r = client.get(f"/api/v1/hr/therapists/{therapist_id}/cases", headers=_headers(hr))
    assert r.status_code == 200
    assert r.json()["therapist_user_id"] == therapist_id
    assert "items" in r.json()
