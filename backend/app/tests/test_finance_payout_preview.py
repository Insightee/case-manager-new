"""Tests for finance therapist payout preview calculations."""
from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.case import BillingType, Case, CompensationMode
from app.services.finance_payout_preview_service import (
    SHADOW_MONTHLY_DAYS,
    calendar_days_for_segment,
    calendar_days_from_start_day,
    calendar_days_incoming,
    calendar_days_outgoing,
    client_lumpsum_inr,
    pay_month_day,
    per_session_share_inr,
    predicted_subtotal_inr,
    therapist_share_inr,
)
from app.seed.demo_seed import run as seed_run

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    seed_run()


def _case(**kwargs) -> Case:
    base = dict(
        id=1,
        case_code="TEST-001",
        child_id=1,
        service_type="Homecare",
        product_module="homecare",
    )
    base.update(kwargs)
    case = Case(**{k: v for k, v in base.items() if k not in ("billing_type", "compensation_mode")})
    if "billing_type" in kwargs:
        case.billing_type = kwargs["billing_type"]
    if "compensation_mode" in kwargs:
        case.compensation_mode = kwargs["compensation_mode"]
    return case


def test_pay_month_day_caps_at_thirty():
    assert pay_month_day(date(2026, 7, 31)) == 30
    assert pay_month_day(date(2026, 7, 15)) == 15


def test_calendar_days_from_start_day():
    assert calendar_days_from_start_day(1) == 30
    assert calendar_days_from_start_day(10) == 20
    assert calendar_days_from_start_day(18) == 12


def test_calendar_days_outgoing_last_session_day():
    assert calendar_days_outgoing(last_session=date(2026, 7, 15), segment_start_day=1) == 15


def test_calendar_days_incoming_from_first_session():
    assert calendar_days_incoming(first_session=date(2026, 7, 18)) == 12


def test_calendar_days_fresh_case_mid_month_assignment():
    days = calendar_days_for_segment(
        is_incoming_replacement=False,
        is_outgoing_replacement=False,
        first_session=date(2026, 7, 12),
        last_session=date(2026, 7, 28),
        assignment_start=date(2026, 7, 10),
        employment_start=None,
        month_start=date(2026, 7, 1),
        month_end=date(2026, 7, 31),
    )
    assert days == 20


def test_calendar_days_replacement_outgoing():
    days = calendar_days_for_segment(
        is_incoming_replacement=False,
        is_outgoing_replacement=True,
        first_session=date(2026, 7, 1),
        last_session=date(2026, 7, 15),
        assignment_start=date(2026, 6, 1),
        employment_start=None,
        month_start=date(2026, 7, 1),
        month_end=date(2026, 7, 31),
    )
    assert days == 15


def test_calendar_days_replacement_incoming():
    days = calendar_days_for_segment(
        is_incoming_replacement=True,
        is_outgoing_replacement=False,
        first_session=date(2026, 7, 18),
        last_session=date(2026, 7, 29),
        assignment_start=date(2026, 7, 17),
        employment_start=None,
        month_start=date(2026, 7, 1),
        month_end=date(2026, 7, 31),
    )
    assert days == 12


def test_calendar_days_new_hire_employment_start():
    days = calendar_days_for_segment(
        is_incoming_replacement=False,
        is_outgoing_replacement=False,
        first_session=date(2026, 7, 12),
        last_session=date(2026, 7, 28),
        assignment_start=date(2026, 6, 1),
        employment_start=date(2026, 7, 10),
        month_start=date(2026, 7, 1),
        month_end=date(2026, 7, 31),
    )
    assert days == 20


def test_homecare_per_session_share_is_flat_inr():
    case = _case(
        billing_type=BillingType.PER_SESSION,
        compensation_mode=CompensationMode.PERCENTAGE,
        pay_share_amount_inr=800,
    )
    assert therapist_share_inr(case) == 800
    assert per_session_share_inr(case) == 800
    assert predicted_subtotal_inr(case, approved_sessions=5, calendar_days=30, unpaid_leaves=0) == 4000


def test_homecare_package_divides_by_session_count():
    case = _case(
        billing_type=BillingType.PACKAGE,
        compensation_mode=CompensationMode.PERCENTAGE,
        package_session_count=20,
        package_amount_inr=25000,
        pay_share_amount_inr=15000,
    )
    assert client_lumpsum_inr(case) == 25000
    assert per_session_share_inr(case) == 750
    assert predicted_subtotal_inr(case, approved_sessions=8, calendar_days=30, unpaid_leaves=2) == 6000


def test_shadow_uses_calendar_days_minus_unpaid_leaves():
    case = _case(
        service_type="Shadow Support",
        product_module="shadow_support",
        billing_type=BillingType.PACKAGE,
        compensation_mode=CompensationMode.PERCENTAGE,
        package_session_count=30,
        package_amount_inr=30000,
        pay_share_amount_inr=18000,
    )
    assert per_session_share_inr(case) == 600
    assert predicted_subtotal_inr(
        case, approved_sessions=20, calendar_days=30, unpaid_leaves=3
    ) == round(600 * (SHADOW_MONTHLY_DAYS - 3), 2)


def test_shadow_subtotal_uses_calendar_days_not_sessions():
    case = _case(
        product_module="shadow_support",
        billing_type=BillingType.PACKAGE,
        compensation_mode=CompensationMode.PERCENTAGE,
        pay_share_amount_inr=15000,
    )
    full = predicted_subtotal_inr(case, approved_sessions=5, calendar_days=30, unpaid_leaves=0)
    partial = predicted_subtotal_inr(case, approved_sessions=25, calendar_days=20, unpaid_leaves=0)
    assert full == 15000
    assert partial == 10000


def test_b2b_uses_same_calendar_day_pay_as_shadow():
    case = _case(
        service_type="B2B",
        product_module="b2b",
        compensation_mode=CompensationMode.PERCENTAGE,
        pay_share_amount_inr=12000,
    )
    assert predicted_subtotal_inr(
        case, approved_sessions=0, calendar_days=20, unpaid_leaves=2
    ) == round((12000 / 30) * 18, 2)


def _headers(email: str) -> dict:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "demo123"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_finance_payout_preview_report_json():
    headers = _headers("finance@demo.com")
    r = client.get(
        "/api/v1/admin/finance-reports/therapist-payout-preview?billing_month=2026-06",
        headers=headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["reportKey"] == "therapist-payout-preview"
    assert "rows" in body
    if body["rows"]:
        row = body["rows"][0]
        assert "Case ID" in row
        assert "Calendar Days" in row
        assert "Predicted Subtotal" in row
        assert "Per Session Share" in row


def test_finance_payout_preview_report_csv():
    headers = _headers("finance@demo.com")
    r = client.get(
        "/api/v1/admin/finance-reports/therapist-payout-preview?billing_month=2026-06&format=csv",
        headers=headers,
    )
    assert r.status_code == 200
    assert "text/csv" in r.headers.get("content-type", "")
