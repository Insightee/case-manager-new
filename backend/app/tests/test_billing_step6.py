"""Step 6 — flat month, leave/30, package payout separation, legacy add-on mapping."""
from __future__ import annotations

from datetime import date, datetime, timezone
from types import SimpleNamespace

from app.models.billing_step6 import AddOnKind, BillingCalcExceptionCode, EffectiveDateChoice
from app.models.case import BillingType, Case, CaseStatus, CompensationMode
from app.models.leave import LeaveBillingCategory, LeaveType
from app.models.session import SessionStatus
from app.services.billing_ledger_service import EffectiveRatePeriod
from app.services import billing_step6_service as step6


def _case(**kwargs) -> Case:
    case = Case(
        id=kwargs.pop("id", 601),
        case_code=kwargs.pop("case_code", "STEP6-M"),
        child_id=1,
        service_type="Shadow support",
        product_module="shadow_support",
        status=CaseStatus.ACTIVE,
        billing_type=BillingType.MONTHLY_FIXED,
        client_monthly_rate_inr=30000.0,
        compensation_mode=CompensationMode.FIXED_LUMP,
        therapist_fixed_pay_inr=24000.0,
        pay_share_amount_inr=24000.0,
        package_session_count=20,
        package_amount_inr=50000.0,  # client amount — must NOT drive payout
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    for k, v in kwargs.items():
        setattr(case, k, v)
    return case


def test_full_month_feb_apr_jan_are_flat_rate():
    rate = 29000.0
    for year, month, last in ((2026, 2, 28), (2026, 4, 30), (2026, 1, 31)):
        start, end = date(year, month, 1), date(year, month, last)
        periods = [EffectiveRatePeriod(start, end, rate, "normal")]
        amount, _, note = step6.compute_monthly_fixed_amount_v6(
            periods, month_start=start, month_end=end, deductible_leave_dates=[]
        )
        assert amount == rate, f"{year}-{month}: expected {rate}, got {amount}"
        assert "full-month flat" in note


def test_jan_reassignment_split_sums_to_flat_not_31_over_30():
    rate = 31000.0
    start, end = date(2026, 1, 1), date(2026, 1, 31)
    periods = [
        EffectiveRatePeriod(date(2026, 1, 1), date(2026, 1, 15), rate, "a"),
        EffectiveRatePeriod(date(2026, 1, 16), date(2026, 1, 31), rate, "b"),
    ]
    amount, _, _ = step6.compute_monthly_fixed_amount_v6(
        periods, month_start=start, month_end=end, deductible_leave_dates=[]
    )
    assert amount == rate
    assert amount != round((rate / 30) * 31, 2)


def test_one_deductible_leave_day_is_exactly_rate_over_30():
    rate = 30000.0
    start, end = date(2026, 7, 1), date(2026, 7, 31)
    periods = [EffectiveRatePeriod(start, end, rate, "normal")]
    amount, _, note = step6.compute_monthly_fixed_amount_v6(
        periods,
        month_start=start,
        month_end=end,
        deductible_leave_dates=[date(2026, 7, 10)],
    )
    assert amount == round(rate - (rate / 30), 2)
    assert "1×" in note or "leave" in note.lower() or "−" in note


def test_therapist_package_payout_never_uses_client_amount():
    case = _case(package_amount_inr=50000.0, therapist_fixed_pay_inr=20000.0, package_session_count=20)
    # 19 payable units → 20000/20*19 = 19000, NOT 50000/20*19
    payout = step6.therapist_package_payout_amount(case, payable_units=19)
    assert payout == 19000.0
    assert payout != round((50000 / 20) * 19, 2)


def test_package_therapist_leave_not_payable_no_double_deduct():
    effect = step6.package_unit_effect_for_status(SessionStatus.THERAPIST_LEAVE, rule=None)
    assert effect.therapist_payable is False
    assert effect.package_consumed is False
    assert effect.reschedulable is True


def test_child_absent_uses_rule_policy_not_assumption():
    rule = SimpleNamespace(child_absent_therapist_payable=True, package_consumes_on_child_absent=False)
    effect = step6.package_unit_effect_for_status(SessionStatus.CLIENT_ABSENT, rule=rule)
    assert effect.therapist_payable is True
    assert effect.package_consumed is False
    assert effect.reschedulable is True


def test_leave_ladder_paid_never_deducts_unpaid_always():
    paid = step6.classify_leave_day(
        leave_type=LeaveType.ANNUAL,
        billing_category=LeaveBillingCategory.PAID,
        absence_type=None,
        sick_credit_available=False,
        credit_system_exists=True,
    )
    assert paid.deductible is False
    unpaid = step6.classify_leave_day(
        leave_type=LeaveType.UNPAID,
        billing_category=LeaveBillingCategory.UNPAID,
        absence_type=None,
        sick_credit_available=True,
        credit_system_exists=True,
    )
    assert unpaid.deductible is True


def test_sick_missing_credit_balance_is_exception_not_silent_deduct():
    d = step6.classify_leave_day(
        leave_type=LeaveType.SICK,
        billing_category=None,
        absence_type=None,
        sick_credit_available=None,
        credit_system_exists=True,
    )
    assert d.deductible is False
    assert d.exception_code == BillingCalcExceptionCode.MISSING_LEAVE_CREDIT_BALANCE.value


def test_legacy_is_additional_visit_maps_to_extra_day_without_kind():
    sess = SimpleNamespace(add_on_kind=None, is_additional_visit=True, parent_session_id=None)
    assert step6.effective_add_on_kind(sess) == AddOnKind.EXTRA_DAY
    # Explicit kind wins
    sess2 = SimpleNamespace(add_on_kind="EXTENDED_SESSION", is_additional_visit=True)
    assert step6.effective_add_on_kind(sess2) == AddOnKind.EXTENDED_SESSION


def test_missing_add_on_rate_surfaces_exception():
    case = _case(billing_type=BillingType.PACKAGE, client_rate_per_session_inr=None)
    sess = SimpleNamespace(add_on_kind="EXTRA_DAY", is_additional_visit=True)
    amount, err = step6.add_on_client_amount(case, sess)
    assert amount is None
    assert err == BillingCalcExceptionCode.MISSING_ADD_ON_RATE.value


def test_resolve_start_of_month_and_change_date():
    # db unused for these two choices
    class _DB:
        def scalars(self, *_a, **_k):
            return self

        def first(self):
            return None

    start, err = step6.resolve_effective_date(
        _DB(),
        case_id=1,
        choice=EffectiveDateChoice.START_OF_MONTH,
        change_date=None,
        approval_at=None,
        billing_month="2026-07",
    )
    assert start == date(2026, 7, 1) and err is None
    start2, err2 = step6.resolve_effective_date(
        _DB(),
        case_id=1,
        choice=EffectiveDateChoice.CHANGE_DATE,
        change_date=date(2026, 7, 12),
        approval_at=None,
        billing_month="2026-07",
    )
    assert start2 == date(2026, 7, 12) and err2 is None


def test_inclusive_adjacent_windows_not_a_gap():
    a = step6.clip_inclusive(date(2026, 7, 1), date(2026, 7, 14), date(2026, 7, 1), date(2026, 7, 31))
    b = step6.clip_inclusive(date(2026, 7, 15), None, date(2026, 7, 1), date(2026, 7, 31))
    assert a == (date(2026, 7, 1), date(2026, 7, 14))
    assert b == (date(2026, 7, 15), date(2026, 7, 31))
    # Adjacent: A's end + 1 day == B's start → not an overlap
    assert a[1] < b[0]
    from datetime import timedelta

    assert a[1] + timedelta(days=1) == b[0]
