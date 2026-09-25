"""Staff employment, probation leave cap, and SPOT access."""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app.core.permissions import RoleName
from app.main import app
from app.models.leave import LeaveBillingCategory, LeaveStatus
from app.models.staff_leave import StaffLeave
from app.models.user import StaffEmploymentType, User
from app.seed.demo_seed import get_or_create_user, run as seed_run
from app.services import staff_employment_service as employment

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def _seed():
    seed_run()


def _login(email: str, portal: str = "staff") -> str:
    r = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "demo123", "portal": portal},
    )
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_spot_login_and_minimal_attendance():
    token = _login("spot@demo.com")
    r = client.get("/api/v1/staff-attendance/me/today", headers=_headers(token))
    assert r.status_code == 200
    r = client.post("/api/v1/staff-attendance/forgot", headers=_headers(token), json={
        "work_date": date.today().isoformat(),
        "start_at": "2026-01-01T09:00:00+05:30",
        "end_at": "2026-01-01T18:00:00+05:30",
        "work_summary": "test",
        "reason": "test forgot",
    })
    assert r.status_code == 403


def test_probation_one_paid_leave_per_month():
    db = SessionLocal()
    try:
        user = get_or_create_user(
            db,
            "prob.staff@demo.com",
            "demo123",
            "Prob Staff",
            RoleName.HR.value,
        )
        employment.apply_staff_employment_fields(
            user,
            employment_type=StaffEmploymentType.PROBATION,
            probation_months=3,
            employment_start_date=date.today().replace(day=1),
            leave_credit_balance=12,
        )
        db.commit()
        db.refresh(user)

        leave_date = date.today().replace(day=10)
        cat1 = employment.preview_staff_leave_billing_category(db, user, leave_date)
        assert cat1 == LeaveBillingCategory.PAID

        db.add(
            StaffLeave(
                staff_user_id=user.id,
                leave_date=leave_date,
                reason="First paid",
                billing_category=LeaveBillingCategory.PAID,
                status=LeaveStatus.APPROVED,
            )
        )
        db.commit()

        leave_date2 = leave_date.replace(day=12)
        cat2 = employment.preview_staff_leave_billing_category(db, user, leave_date2)
        assert cat2 == LeaveBillingCategory.UNPAID
    finally:
        db.close()


def test_admin_home_spot_variant():
    token = _login("spot@demo.com")
    r = client.get("/api/v1/admin/home", headers=_headers(token))
    assert r.status_code == 200
    data = r.json()
    assert data.get("role") == "SPOT"
    assert data.get("dashboard_variant") == "spot"
