"""Release-gate integration coverage for Finance Engine Steps 1–6.

Exercises calculator + invoice/payout attribution paths used in production services,
not only isolated helpers.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.assignment import CaseAssignment, CaseAssignmentStatus
from app.models.billing_step6 import BillingCalcExceptionCode
from app.models.case import BillingType, Case, CaseStatus, CompensationMode
from app.models.daily_log import DailyLog, LogApprovalStatus
from app.models.ledger_billing import BillableStatus, BillingLedger
from app.models.session import Session as TherapySession
from app.models.session import SessionMode, SessionStatus
from app.models.user import User
from app.services import billing_ledger_service, billing_step6_service as step6
from app.services import invoice_billing_service
from app.services.billing_ledger_service import EffectiveRatePeriod


def _monthly_case(**kwargs) -> Case:
    case = Case(
        id=kwargs.pop("id", 901),
        case_code=kwargs.pop("case_code", "REL-M"),
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
        package_amount_inr=50000.0,
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    for k, v in kwargs.items():
        setattr(case, k, v)
    return case


@pytest.mark.parametrize(
    "year,month,last",
    [(2026, 1, 31), (2026, 2, 28)],
)
def test_01_02_full_monthly_fixed_is_flat_rate(year, month, last):
    rate = 29000.0
    start, end = date(year, month, 1), date(year, month, last)
    amount, _, note = step6.compute_monthly_fixed_amount_v6(
        [EffectiveRatePeriod(start, end, rate, "normal")],
        month_start=start,
        month_end=end,
        deductible_leave_dates=[],
    )
    assert amount == rate
    assert "full-month flat" in note


def test_03_one_deductible_leave_is_rate_over_30():
    rate = 30000.0
    start, end = date(2026, 7, 1), date(2026, 7, 31)
    amount, _, _ = step6.compute_monthly_fixed_amount_v6(
        [EffectiveRatePeriod(start, end, rate, "normal")],
        month_start=start,
        month_end=end,
        deductible_leave_dates=[date(2026, 7, 10)],
    )
    assert amount == round(rate - (rate / 30), 2)


def test_04_mid_month_reassignment_attribution_uses_date_active_assignment():
    """SQL already filters start_date <= on_date; mock each call's covering rows."""
    a1 = SimpleNamespace(
        therapist_user_id=11,
        start_date=date(2026, 7, 1),
        end_date=date(2026, 7, 15),
        status=CaseAssignmentStatus.ACTIVE,
    )
    a2 = SimpleNamespace(
        therapist_user_id=22,
        start_date=date(2026, 7, 16),
        end_date=None,
        status=CaseAssignmentStatus.ACTIVE,
    )

    def _check(rows, therapist_id, on_date):
        db = MagicMock()
        db.scalars.return_value.all.return_value = rows
        return invoice_billing_service.therapist_active_on_session_date(
            db, case_id=1, therapist_user_id=therapist_id, on_date=on_date
        )

    ok_early, code_early = _check([a1], 11, date(2026, 7, 10))
    ok_late, code_late = _check([a2], 22, date(2026, 7, 20))
    bad, bad_code = _check([a2], 11, date(2026, 7, 20))
    assert ok_early and code_early is None
    assert ok_late and code_late is None
    assert not bad and bad_code == "ASSIGNMENT_GAP"


def test_05_assignment_gap_no_guessed_payout():
    db = MagicMock()
    a1 = SimpleNamespace(
        therapist_user_id=11,
        start_date=date(2026, 7, 1),
        end_date=date(2026, 7, 31),
        status=CaseAssignmentStatus.ACTIVE,
    )
    db.scalars.return_value.all.return_value = [a1]
    ok, code = invoice_billing_service.therapist_active_on_session_date(
        db, case_id=1, therapist_user_id=99, on_date=date(2026, 7, 10)
    )
    assert ok is False
    assert code == "ASSIGNMENT_GAP"


def test_06_assignment_overlap_no_guessed_payout():
    db = MagicMock()
    a1 = SimpleNamespace(
        therapist_user_id=11,
        start_date=date(2026, 7, 1),
        end_date=None,
        status=CaseAssignmentStatus.ACTIVE,
    )
    a2 = SimpleNamespace(
        therapist_user_id=22,
        start_date=date(2026, 7, 1),
        end_date=None,
        status=CaseAssignmentStatus.ACTIVE,
    )
    db.scalars.return_value.all.return_value = [a1, a2]
    ok, code = invoice_billing_service.therapist_active_on_session_date(
        db, case_id=1, therapist_user_id=11, on_date=date(2026, 7, 10)
    )
    assert ok is False
    assert code == "ASSIGNMENT_OVERLAP"


def test_07_missing_package_count_raises():
    case = _monthly_case(billing_type=BillingType.PACKAGE, package_session_count=None)
    with pytest.raises(ValueError) as exc:
        step6.therapist_package_payout_amount(case, payable_units=1)
    assert BillingCalcExceptionCode.MISSING_PACKAGE_COUNT.value in str(exc.value)


def test_08_therapist_package_payout_ignores_client_amount():
    case = _monthly_case(
        billing_type=BillingType.PACKAGE,
        package_amount_inr=99999.0,
        therapist_fixed_pay_inr=20000.0,
        package_session_count=10,
    )
    payout = step6.therapist_package_payout_amount(case, payable_units=5)
    assert payout == 10000.0


def test_09_therapist_leave_not_payable_once():
    effect = step6.package_unit_effect_for_status(SessionStatus.THERAPIST_LEAVE, rule=None)
    assert effect.therapist_payable is False
    assert effect.package_consumed is False


def test_10_11_child_absent_therapist_payable_flags():
    rule_true = SimpleNamespace(child_absent_therapist_payable=True, package_consumes_on_child_absent=False)
    rule_false = SimpleNamespace(child_absent_therapist_payable=False, package_consumes_on_child_absent=False)
    assert step6.package_unit_effect_for_status(SessionStatus.CLIENT_ABSENT, rule=rule_true).therapist_payable is True
    assert step6.package_unit_effect_for_status(SessionStatus.CLIENT_ABSENT, rule=rule_false).therapist_payable is False


def test_12_13_child_absent_package_consume_flags():
    rule_true = SimpleNamespace(child_absent_therapist_payable=False, package_consumes_on_child_absent=True)
    rule_false = SimpleNamespace(child_absent_therapist_payable=False, package_consumes_on_child_absent=False)
    assert step6.package_unit_effect_for_status(SessionStatus.CLIENT_ABSENT, rule=rule_true).package_consumed is True
    assert step6.package_unit_effect_for_status(SessionStatus.CLIENT_ABSENT, rule=rule_false).package_consumed is False


def test_14_15_add_on_rate_or_missing_exception():
    case_ok = _monthly_case(billing_type=BillingType.PER_SESSION, client_rate_per_session_inr=1500.0)
    case_bad = _monthly_case(billing_type=BillingType.PER_SESSION, client_rate_per_session_inr=None)
    session = SimpleNamespace(add_on_kind="EXTRA_DAY", is_additional_visit=True)
    amount, err = step6.add_on_client_amount(case_ok, session)
    assert amount == 1500.0 and err is None
    amount2, err2 = step6.add_on_client_amount(case_bad, session)
    assert amount2 is None and err2 == BillingCalcExceptionCode.MISSING_ADD_ON_RATE.value


def test_16_billing_ledger_writes_false_blocks_outside_test_env(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "billing_ledger_writes", False)
    assert billing_ledger_service._ledger_writes_allowed() is False
    db = SessionLocal()
    try:
        therapist = db.scalars(select(User).where(User.email == "therapist@demo.com")).first()
        assert therapist
        assignment = db.scalars(
            select(CaseAssignment).where(
                CaseAssignment.therapist_user_id == therapist.id,
                CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
            )
        ).first()
        assert assignment
        case = db.get(Case, assignment.case_id)
        case.billing_type = BillingType.PER_SESSION
        case.client_rate_per_session_inr = case.client_rate_per_session_inr or 1500.0
        started = datetime.now(timezone.utc) - timedelta(hours=1)
        ended = started + timedelta(minutes=40)
        session = TherapySession(
            case_id=case.id,
            therapist_user_id=therapist.id,
            scheduled_date=date(2026, 8, 1),
            start_time=time(10, 0),
            end_time=time(11, 0),
            mode=SessionMode.HOME,
            status=SessionStatus.COMPLETED,
            actual_start_at=started,
            actual_end_at=ended,
        )
        db.add(session)
        db.flush()
        assert billing_ledger_service.sync_session_status(db, session) is None
        rows = db.scalars(select(BillingLedger).where(BillingLedger.session_id == session.id)).all()
        assert rows == []
        db.rollback()
    finally:
        db.close()


def test_17_read_only_finance_paths_safe_when_writes_disabled(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "billing_ledger_writes", False)
    monkeypatch.setattr(settings, "enable_billing", False)
    db = SessionLocal()
    try:
        summary = billing_ledger_service.eligibility_exceptions_summary(db, ledger_month="2026-07")
        assert "logHoldCount" in summary
        flags = billing_ledger_service.list_period_flags(db, ledger_month="2026-07")
        assert isinstance(flags, list)
    finally:
        db.close()
