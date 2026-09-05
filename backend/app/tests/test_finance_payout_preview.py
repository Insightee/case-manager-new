"""Tests for finance therapist payout preview calculations."""
from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.database import SessionLocal
from app.main import app
from app.models.case import BillingType, Case, CompensationMode
from app.models.leave import LeaveBillingCategory, LeaveStatus, LeaveType, TherapistLeave
from app.models.user import User
from app.services.finance_payout_preview_service import (
    DEMO_CALENDAR_SEED_MONTHS,
    SHADOW_MONTHLY_DAYS,
    apply_therapist_total_column,
    calendar_days_for_segment,
    calendar_days_from_start_day,
    calendar_days_incoming,
    calendar_days_outgoing,
    classify_outgoing_calendar_day_segments,
    client_configured_share_inr,
    client_lumpsum_inr,
    diff_calendar_day_clamp_snapshots,
    freeze_outgoing_clamp_scope,
    freeze_payout_identities,
    is_demo_calendar_seed_month,
    pay_month_day,
    per_session_share_inr,
    predicted_client_amount_inr,
    predicted_subtotal_inr,
    therapist_share_inr,
)
from app.services.reports_export_helpers import (
    leave_applies_to_case,
    leave_days_in_month,
    leave_days_in_month_for_case,
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


def test_client_configured_share_uses_allotment_not_therapist_pay():
    shadow = _case(
        service_type="Shadow Support",
        product_module="shadow_support",
        billing_type=BillingType.PACKAGE,
        package_amount_inr=30000,
        pay_share_amount_inr=18000,
    )
    assert client_configured_share_inr(shadow) == 30000
    assert predicted_client_amount_inr(
        shadow, approved_sessions=20, calendar_days=10, unpaid_leaves=0
    ) == round((30000 / 30) * 10, 2)

    homecare = _case(
        billing_type=BillingType.PER_SESSION,
        client_rate_per_session_inr=1200,
        pay_share_amount_inr=800,
    )
    assert client_configured_share_inr(homecare) == 1200
    assert predicted_client_amount_inr(homecare, approved_sessions=5, calendar_days=30) == 6000


def test_homecare_package_client_is_package_over_count_times_sessions():
    case = _case(
        billing_type=BillingType.PACKAGE,
        package_session_count=20,
        package_amount_inr=25000,
        pay_share_amount_inr=15000,
    )
    assert client_configured_share_inr(case) == 25000
    assert predicted_client_amount_inr(case, approved_sessions=10) == 12500


def test_split_month_client_charge_sums_therapist_calendar_days():
    """Outgoing 10 days + incoming 10 days → family pays 20/30 of client lump."""
    case = _case(
        product_module="shadow_support",
        billing_type=BillingType.PACKAGE,
        package_amount_inr=30000,
        pay_share_amount_inr=18000,
    )
    outgoing = predicted_client_amount_inr(case, approved_sessions=0, calendar_days=10, unpaid_leaves=0)
    incoming = predicted_client_amount_inr(case, approved_sessions=0, calendar_days=10, unpaid_leaves=0)
    assert round(outgoing + incoming, 2) == round((30000 / 30) * 20, 2)
    assert predicted_subtotal_inr(case, approved_sessions=0, calendar_days=10, unpaid_leaves=0) == 6000


def test_shadow_per_session_client_share_is_rate_times_thirty():
    case = _case(
        product_module="shadow_support",
        billing_type=BillingType.PER_SESSION,
        client_rate_per_session_inr=1000,
        pay_share_amount_inr=600,
    )
    assert client_configured_share_inr(case) == 30000
    assert predicted_client_amount_inr(case, approved_sessions=8, calendar_days=10, unpaid_leaves=0) == 10000
    assert predicted_subtotal_inr(case, approved_sessions=8, calendar_days=10, unpaid_leaves=0) == 200


def test_pay_month_day_caps_at_thirty():
    assert pay_month_day(date(2026, 7, 31)) == 30
    assert pay_month_day(date(2026, 7, 15)) == 15


def test_calendar_days_from_start_day_inclusive():
    assert calendar_days_from_start_day(1) == 30
    assert calendar_days_from_start_day(10) == 21
    assert calendar_days_from_start_day(15) == 16
    assert calendar_days_from_start_day(18) == 13


def test_calendar_days_outgoing_last_log_day():
    assert calendar_days_outgoing(last_log=date(2026, 7, 15), segment_start_day=1) == 15
    assert calendar_days_outgoing(last_log=date(2026, 7, 20), segment_start_day=10) == 11


def test_calendar_days_incoming_from_first_log():
    assert calendar_days_incoming(first_log=date(2026, 7, 18)) == 13
    assert calendar_days_incoming(first_log=date(2026, 7, 15)) == 16


def test_calendar_days_fresh_case_mid_month_assignment():
    days = calendar_days_for_segment(
        is_incoming_replacement=False,
        is_outgoing_replacement=False,
        first_log=date(2026, 7, 12),
        last_log=date(2026, 7, 28),
        assignment_start=date(2026, 7, 10),
        employment_start=None,
        month_start=date(2026, 7, 1),
        month_end=date(2026, 7, 31),
    )
    assert days == 21


def test_calendar_days_replacement_outgoing():
    days = calendar_days_for_segment(
        is_incoming_replacement=False,
        is_outgoing_replacement=True,
        first_log=date(2026, 7, 1),
        last_log=date(2026, 7, 15),
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
        first_log=date(2026, 7, 18),
        last_log=date(2026, 7, 29),
        assignment_start=date(2026, 7, 17),
        employment_start=None,
        month_start=date(2026, 7, 1),
        month_end=date(2026, 7, 31),
    )
    assert days == 13


def test_calendar_days_future_segment_end_uses_in_month_last_log():
    """IC-2026-SS-029 repro: July segment_end must not zero June payout."""
    days = calendar_days_for_segment(
        is_incoming_replacement=False,
        is_outgoing_replacement=True,
        first_log=date(2026, 6, 4),
        last_log=date(2026, 6, 28),
        assignment_start=date(2026, 6, 4),
        employment_start=None,
        month_start=date(2026, 6, 1),
        month_end=date(2026, 6, 30),
        segment_end=date(2026, 7, 3),
    )
    assert days == 25


def test_calendar_days_future_segment_end_no_in_month_logs_returns_zero():
    days = calendar_days_for_segment(
        is_incoming_replacement=False,
        is_outgoing_replacement=True,
        first_log=None,
        last_log=None,
        assignment_start=date(2026, 6, 4),
        employment_start=None,
        month_start=date(2026, 6, 1),
        month_end=date(2026, 6, 30),
        segment_end=date(2026, 7, 3),
    )
    assert days == 0


def test_calendar_days_segment_closed_before_billing_month_returns_zero():
    days = calendar_days_for_segment(
        is_incoming_replacement=False,
        is_outgoing_replacement=True,
        first_log=None,
        last_log=None,
        assignment_start=date(2026, 5, 1),
        employment_start=None,
        month_start=date(2026, 6, 1),
        month_end=date(2026, 6, 30),
        segment_end=date(2026, 5, 20),
    )
    assert days == 0


def test_calendar_days_genuine_june_exit_unchanged():
    """In-month segment_end is a no-op for correctly-paid outgoing cases."""
    days = calendar_days_for_segment(
        is_incoming_replacement=False,
        is_outgoing_replacement=True,
        first_log=date(2026, 6, 1),
        last_log=date(2026, 6, 12),
        assignment_start=date(2026, 6, 1),
        employment_start=None,
        month_start=date(2026, 6, 1),
        month_end=date(2026, 6, 30),
        segment_end=date(2026, 6, 12),
    )
    assert days == 12


def test_calendar_days_non_outgoing_ongoing_unchanged():
    days = calendar_days_for_segment(
        is_incoming_replacement=False,
        is_outgoing_replacement=False,
        first_log=date(2026, 6, 1),
        last_log=date(2026, 6, 28),
        assignment_start=date(2026, 6, 1),
        employment_start=None,
        month_start=date(2026, 6, 1),
        month_end=date(2026, 6, 30),
        segment_end=None,
    )
    assert days == 30


def test_calendar_days_never_exceeds_first_log_through_month_end():
    month_start = date(2026, 6, 1)
    month_end = date(2026, 6, 30)
    first_log = date(2026, 6, 4)
    days = calendar_days_for_segment(
        is_incoming_replacement=False,
        is_outgoing_replacement=True,
        first_log=first_log,
        last_log=date(2026, 6, 28),
        assignment_start=date(2026, 6, 4),
        employment_start=None,
        month_start=month_start,
        month_end=month_end,
        segment_end=date(2026, 7, 3),
    )
    assert days <= calendar_days_from_start_day(pay_month_day(first_log))


def test_calendar_days_outgoing_july_last_log_in_june_month_is_zero():
    days = calendar_days_for_segment(
        is_incoming_replacement=False,
        is_outgoing_replacement=True,
        first_log=date(2026, 7, 1),
        last_log=date(2026, 7, 3),
        assignment_start=date(2026, 5, 1),
        employment_start=None,
        month_start=date(2026, 6, 1),
        month_end=date(2026, 6, 30),
        segment_end=date(2026, 7, 15),
    )
    assert days == 0
    assert calendar_days_outgoing(last_log=date(2026, 7, 3), segment_start_day=1) == 3


def test_calendar_days_outgoing_future_end_last_log_before_month_is_zero():
    days = calendar_days_for_segment(
        is_incoming_replacement=False,
        is_outgoing_replacement=True,
        first_log=date(2026, 5, 10),
        last_log=date(2026, 5, 28),
        assignment_start=date(2026, 5, 1),
        employment_start=None,
        month_start=date(2026, 6, 1),
        month_end=date(2026, 6, 30),
        segment_end=date(2026, 7, 3),
    )
    assert days == 0


def test_calendar_days_out_of_month_end_cannot_increase_vs_in_month_evidence():
    month_start = date(2026, 6, 1)
    month_end = date(2026, 6, 30)
    for last_day in (1, 10, 15, 20, 30):
        last_log = date(2026, 6, last_day)
        kwargs = dict(
            is_incoming_replacement=False,
            is_outgoing_replacement=True,
            first_log=date(2026, 6, 1),
            last_log=last_log,
            assignment_start=date(2026, 5, 1),
            employment_start=None,
            month_start=month_start,
            month_end=month_end,
        )
        in_month_days = calendar_days_for_segment(**kwargs, segment_end=last_log)
        stretched = calendar_days_for_segment(**kwargs, segment_end=date(2026, 7, 3))
        assert stretched <= in_month_days
        assert stretched == last_day


def test_homecare_per_session_pay_ignores_calendar_days():
    case = _case(
        billing_type=BillingType.PER_SESSION,
        compensation_mode=CompensationMode.PERCENTAGE,
        pay_share_amount_inr=800,
    )
    short = predicted_subtotal_inr(case, approved_sessions=5, calendar_days=3)
    full = predicted_subtotal_inr(case, approved_sessions=5, calendar_days=30)
    assert short == full == 4000


def test_calendar_days_new_hire_employment_start():
    days = calendar_days_for_segment(
        is_incoming_replacement=False,
        is_outgoing_replacement=False,
        first_log=date(2026, 7, 12),
        last_log=date(2026, 7, 28),
        assignment_start=date(2026, 6, 1),
        employment_start=date(2026, 7, 10),
        month_start=date(2026, 7, 1),
        month_end=date(2026, 7, 31),
    )
    assert days == 21


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


def test_client_lumpsum_fills_per_session_and_monthly():
    """Client Amount (INR) must not be blank for non-package billing."""
    per_session = _case(
        billing_type=BillingType.PER_SESSION,
        compensation_mode=CompensationMode.FIXED_LUMP,
        client_rate_per_session_inr=1200,
        therapist_fixed_pay_inr=840,
    )
    assert client_lumpsum_inr(per_session) == 1200

    monthly = _case(
        billing_type=BillingType.MONTHLY_FIXED,
        compensation_mode=CompensationMode.FIXED_LUMP,
        client_monthly_rate_inr=18000,
        therapist_fixed_pay_inr=9000,
    )
    assert client_lumpsum_inr(monthly) == 18000

    empty = _case(billing_type=BillingType.PER_SESSION, client_rate_per_session_inr=None)
    assert client_lumpsum_inr(empty) is None


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
    partial = predicted_subtotal_inr(case, approved_sessions=25, calendar_days=21, unpaid_leaves=0)
    assert full == 15000
    assert partial == 10500


def test_b2b_uses_same_calendar_day_pay_as_shadow():
    case = _case(
        service_type="B2B",
        product_module="b2b",
        compensation_mode=CompensationMode.PERCENTAGE,
        pay_share_amount_inr=12000,
    )
    assert predicted_subtotal_inr(
        case, approved_sessions=0, calendar_days=21, unpaid_leaves=2
    ) == round((12000 / 30) * 19, 2)


def test_leave_applies_to_case():
    leave_on_case = TherapistLeave(
        therapist_user_id=1,
        leave_type=LeaveType.ANNUAL,
        start_date=date(2026, 7, 1),
        end_date=date(2026, 7, 1),
        status=LeaveStatus.APPROVED,
        case_id=10,
        case_ids=[10],
    )
    leave_wide = TherapistLeave(
        therapist_user_id=1,
        leave_type=LeaveType.CASUAL,
        start_date=date(2026, 7, 2),
        end_date=date(2026, 7, 2),
        status=LeaveStatus.APPROVED,
    )
    assert leave_applies_to_case(leave_on_case, 10) is True
    assert leave_applies_to_case(leave_on_case, 99) is False
    assert leave_applies_to_case(leave_wide, 10) is False


def test_leave_days_in_month_for_case_scoped():
    db = SessionLocal()
    try:
        therapist = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
        cases = db.scalars(select(Case).limit(2)).all()
        if not therapist or len(cases) < 2:
            pytest.skip("Need therapist and two cases")
        case_a, case_b = cases[0], cases[1]
        ym = "2026-09"
        from datetime import time as dt_time

        from app.models.session import Session as TherapySession
        from app.models.session import SessionMode, SessionStatus

        for day in (date(2026, 9, 5), date(2026, 9, 6)):
            db.add(
                TherapySession(
                    case_id=case_a.id,
                    therapist_user_id=therapist.id,
                    scheduled_date=day,
                    start_time=dt_time(9, 0),
                    end_time=dt_time(10, 0),
                    mode=SessionMode.SCHOOL,
                    status=SessionStatus.SCHEDULED,
                )
            )
        db.add(
            TherapistLeave(
                therapist_user_id=therapist.id,
                leave_type=LeaveType.ANNUAL,
                billing_category=LeaveBillingCategory.UNPAID,
                paid_days=0,
                unpaid_days=2,
                start_date=date(2026, 9, 5),
                end_date=date(2026, 9, 6),
                status=LeaveStatus.APPROVED,
                case_id=case_a.id,
                case_ids=[case_a.id],
            )
        )
        db.commit()
        scoped_a = leave_days_in_month_for_case(db, therapist.id, case_a.id, ym)
        scoped_b = leave_days_in_month_for_case(db, therapist.id, case_b.id, ym)
        total = leave_days_in_month(db, therapist.id, ym)
        assert scoped_a["unpaid"] >= 2
        assert scoped_b["unpaid"] == 0
        assert total["unpaid"] >= scoped_a["unpaid"]
    finally:
        db.close()


def _headers(email: str) -> dict:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "demo123"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_apply_therapist_total_column_first_row_only():
    rows = [
        {"Therapist Name": "Alice", "Therapist ID": "T1", "Case ID": "C1", "Predicted Total": 5000},
        {"Therapist Name": "Alice", "Therapist ID": "T1", "Case ID": "C2", "Predicted Total": 4000},
        {"Therapist Name": "Bob", "Therapist ID": "T2", "Case ID": "C3", "Predicted Total": 8000},
    ]
    result = apply_therapist_total_column(rows)
    assert result[0]["Therapist Total"] == 9000
    assert result[1]["Therapist Total"] == ""
    assert result[2]["Therapist Total"] == 8000
    assert list(result[0].keys())[-1] == "Therapist Total"


def test_normalize_legacy_share_column_headers():
    from app.services.finance_payout_preview_service import normalize_payout_preview_row

    row = normalize_payout_preview_row(
        {
            "Therapist Share": 4500,
            "Per Session Share": 150,
            "Lumpsum Amount": 12000,
            "Predicted Total": 4500,
            "Therapist ID": "T9",
        }
    )
    assert row["Therapist Pay (INR)"] == 4500
    assert row["Therapist Unit Pay (INR)"] == 150
    assert row["Client Amount (INR)"] == 12000
    assert "Therapist Share" not in row
    assert "Per Session Share" not in row
    assert "Lumpsum Amount" not in row
    assert "Per Session Pay (INR)" not in row


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
    assert "generatedBy" in body
    assert "generatedAt" in body
    assert "IST" in body["generatedAt"]
    if body["rows"]:
        row = body["rows"][0]
        assert "Case ID" in row
        assert "Client Name" in row
        assert "Parent Name" in row
        keys = list(row.keys())
        assert keys.index("Parent Name") == keys.index("Client Name") + 1
        assert "Therapist Start Date" in row
        assert "Case Start Date" in row
        assert "Case End Date" in row
        assert "Calendar Days" in row
        assert "Predicted Subtotal" in row
        assert "Transition Days" in row
        assert "Transition Day Type" in row
        assert "Transition Days Total Amount" in row
        assert "Predicted Total" in row
        assert "Billing Type" in row
        assert "Client Amount (INR)" in row
        assert "Therapist Pay (INR)" in row
        assert "Therapist Unit Pay (INR)" in row
        assert "Lumpsum Amount" not in row
        assert "Therapist Share" not in row
        assert "Per Session Share" not in row
        assert "Per Session Pay (INR)" not in row
        assert "Therapist Total" in row
        # Homecare per-session must carry client amount (not blank package-only lumpsum)
        per_session_rows = [r for r in body["rows"] if r.get("Billing Type") == "PER_SESSION"]
        if per_session_rows:
            assert any(r.get("Client Amount (INR)") not in (None, "") for r in per_session_rows)


def test_finance_payout_preview_report_csv():
    headers = _headers("finance@demo.com")
    r = client.get(
        "/api/v1/admin/finance-reports/therapist-payout-preview?billing_month=2026-06&format=csv",
        headers=headers,
    )
    assert r.status_code == 200
    assert "text/csv" in r.headers.get("content-type", "")


def test_finance_payout_preview_report_xlsx():
    headers = _headers("finance@demo.com")
    r = client.get(
        "/api/v1/admin/finance-reports/therapist-payout-preview?billing_month=2026-06&format=xlsx",
        headers=headers,
    )
    assert r.status_code == 200
    assert "spreadsheetml" in r.headers.get("content-type", "")


def test_demo_seed_months_are_not_live_clamp_merge_gate():
    assert is_demo_calendar_seed_month("2026-06")
    assert "2026-05" in DEMO_CALENDAR_SEED_MONTHS
    assert "2026-07" in DEMO_CALENDAR_SEED_MONTHS
    assert not is_demo_calendar_seed_month("2026-08")


def test_classify_outgoing_calendar_day_segments_id_only():
    db = SessionLocal()
    try:
        rows = classify_outgoing_calendar_day_segments(db, "2026-06")
        forbidden = {"Client Name", "Parent Name", "Therapist Name", "child_name"}
        for row in rows:
            assert forbidden.isdisjoint(row.keys())
            assert "case_id" in row
            assert "therapist_user_id" in row
            assert row["class"] in {
                "out_of_month_end",
                "pre_month_closed",
                "control",
                "unbounded_outgoing",
            }
        freeze = freeze_outgoing_clamp_scope(rows)
        identities = freeze_payout_identities(rows)
        assert len(identities) == len(freeze)
        for row in freeze:
            assert row["class"] in {"out_of_month_end", "pre_month_closed"}
            assert row["is_demo_seed_month"] is True
    finally:
        db.close()


def test_diff_calendar_day_clamp_snapshots_bounds_columns_and_rows():
    identity = ("12", "4", "2026-05-01", "2026-07-03")
    before = {
        "payout_rows": [
            {
                "case_id": 12,
                "therapist_user_id": 4,
                "segment_start": "2026-05-01",
                "segment_end": "2026-07-03",
                "calendar_days": 3,
                "approved_sessions": 8,
                "therapist_gross_inr": 600.0,
                "client_amount_inr": 1000.0,
                "billing_type": "PACKAGE",
                "uses_calendar_day_pay": True,
            },
            {
                "case_id": 99,
                "therapist_user_id": 8,
                "segment_start": "2026-06-01",
                "segment_end": "",
                "calendar_days": 30,
                "approved_sessions": 20,
                "therapist_gross_inr": 15000.0,
                "client_amount_inr": 30000.0,
                "billing_type": "PACKAGE",
                "uses_calendar_day_pay": True,
            },
        ],
        "client_rows": [
            {
                "case_id": 12,
                "billing_type": "PACKAGE",
                "uses_calendar_day_pay": True,
                "client_gross_inr": 1000.0,
                "calendar_days": 3,
                "approved_sessions": 8,
                "package_amount_inr": 30000,
            },
            {
                "case_id": 99,
                "billing_type": "PACKAGE",
                "uses_calendar_day_pay": True,
                "client_gross_inr": 30000.0,
                "calendar_days": 30,
                "approved_sessions": 20,
                "package_amount_inr": 30000,
            },
            {
                "case_id": 50,
                "billing_type": "PER_SESSION",
                "uses_calendar_day_pay": False,
                "client_gross_inr": 6000.0,
                "calendar_days": 0,
                "approved_sessions": 5,
                "client_rate_per_session_inr": 1200,
            },
        ],
    }
    after = {
        "payout_rows": [
            {
                **before["payout_rows"][0],
                "calendar_days": 20,
                "therapist_gross_inr": 4000.0,
                "client_amount_inr": 6666.67,
            },
            dict(before["payout_rows"][1]),
        ],
        "client_rows": [
            {
                **before["client_rows"][0],
                "client_gross_inr": 6666.67,
                "calendar_days": 20,
            },
            dict(before["client_rows"][1]),
            dict(before["client_rows"][2]),
        ],
    }
    ok = diff_calendar_day_clamp_snapshots(before, after, frozen_identities={identity})
    assert ok["ok"] is True

    leaked = {
        "payout_rows": [
            before["payout_rows"][0],
            {
                **before["payout_rows"][1],
                "calendar_days": 21,
                "therapist_gross_inr": 10500.0,
            },
        ],
        "client_rows": before["client_rows"],
    }
    bad = diff_calendar_day_clamp_snapshots(before, leaked, frozen_identities={identity})
    assert bad["ok"] is False
    assert bad["unexpected_payout"]

    homecare_drift = {
        "payout_rows": before["payout_rows"],
        "client_rows": [
            before["client_rows"][0],
            before["client_rows"][1],
            {**before["client_rows"][2], "approved_sessions": 9},
        ],
    }
    hc = diff_calendar_day_clamp_snapshots(
        before, homecare_drift, frozen_identities={identity}
    )
    assert hc["ok"] is False
    assert hc["unexpected_client"]
