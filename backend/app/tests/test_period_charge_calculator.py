"""Step 2 — four-way client billing calculator (period charges, DRAFT on zero sessions)."""
from __future__ import annotations

from datetime import date, datetime, timezone

from app.models.case import BillingType, Case, CaseStatus, CompensationMode
from app.models.ledger_billing import BillableStatus, LedgerSourceType
from app.services.billing_ledger_service import (
    build_monthly_rate_periods,
    compute_monthly_fixed_amount,
)


def _monthly_case(**kwargs) -> Case:
    case = Case(
        id=kwargs.pop("id", 501),
        case_code=kwargs.pop("case_code", "STEP2-M"),
        child_id=1,
        service_type="Shadow support",
        product_module="shadow_support",
        status=CaseStatus.ACTIVE,
        billing_type=BillingType.MONTHLY_FIXED,
        client_monthly_rate_inr=29000.0,
        client_rate_per_session_inr=None,
        compensation_mode=CompensationMode.PERCENTAGE,
        pay_share_amount_inr=18000.0,
        created_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
    )
    for k, v in kwargs.items():
        setattr(case, k, v)
    return case


def test_monthly_amount_is_not_session_multiplied():
    case = _monthly_case()
    periods = build_monthly_rate_periods(
        case, month_start=date(2026, 7, 1), month_end=date(2026, 7, 31)
    )
    amount, days, note = compute_monthly_fixed_amount(
        periods, month_start=date(2026, 7, 1), month_end=date(2026, 7, 31)
    )
    # Full July → flat monthly rate (not rate/30 × 31)
    assert amount == 29000.0
    assert days == 30
    assert "full-month flat" in note
    # Isa Binoy pattern: must NOT be 29000 * 20
    assert amount != 29000 * 20


def test_partial_month_uses_fixed_30_divisor():
    case = _monthly_case(created_at=datetime(2026, 7, 16, tzinfo=timezone.utc))
    periods = build_monthly_rate_periods(
        case, month_start=date(2026, 7, 1), month_end=date(2026, 7, 31)
    )
    amount, days, _ = compute_monthly_fixed_amount(
        periods, month_start=date(2026, 7, 1), month_end=date(2026, 7, 31)
    )
    # Jul 16–31 = 16 days → 29000/30*16
    assert days == 16
    assert amount == round((29000 / 30) * 16, 2)


def test_retainer_split_sums_sub_periods():
    case = _monthly_case(
        retainer_start_date=date(2026, 7, 1),
        retainer_end_date=date(2026, 7, 10),
        retainer_rate_inr=15000.0,
        client_monthly_rate_inr=30000.0,
    )
    periods = build_monthly_rate_periods(
        case, month_start=date(2026, 7, 1), month_end=date(2026, 7, 31)
    )
    labels = [p.label for p in periods]
    assert "retainer" in labels
    assert "normal" in labels
    amount, days, note = compute_monthly_fixed_amount(
        periods, month_start=date(2026, 7, 1), month_end=date(2026, 7, 31)
    )
    # 10 retainer + 21 normal = 31 calendar days, but billed days capped at 30
    # Allocation: first 10 retainer, then 20 of the 21 normal (cap)
    retainer_part = round((15000 / 30) * 10, 2)
    normal_part = round((30000 / 30) * 20, 2)
    assert days == 30
    assert amount == round(retainer_part + normal_part, 2)
    assert "retainer:" in note and "normal:" in note


def test_ensure_period_charges_zero_sessions_is_pending_finance(db_session=None):
    """Uses service helpers; full DB path covered on staging acceptance."""
    # Pure status rule
    from app.services.billing_ledger_service import _period_billable_status

    assert _period_billable_status(0) == BillableStatus.PENDING_FINANCE
    assert _period_billable_status(1) == BillableStatus.BILLABLE
    assert _period_billable_status(20) == BillableStatus.BILLABLE


def test_blocks_per_session_for_monthly_and_package():
    from app.services.billing_ledger_service import _blocks_per_session_ledger

    monthly = _monthly_case()
    assert _blocks_per_session_ledger(monthly, None) is True
    pkg = _monthly_case(billing_type=BillingType.PACKAGE, package_amount_inr=25000.0)
    assert _blocks_per_session_ledger(pkg, None) is True
    per = _monthly_case(billing_type=BillingType.PER_SESSION, client_rate_per_session_inr=1500.0)
    assert _blocks_per_session_ledger(per, None) is False
