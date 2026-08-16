from datetime import timedelta

import pytest

from app.core.timezone import today_ist
from app.models.case import BillingType, Case, CaseDayType, CompensationMode
from app.models.invoice_line import SessionLineType
from app.services import invoice_billing_service, therapist_transition_service


def test_transition_dates_reject_past_days() -> None:
    today = today_ist()
    values = [
        (today - timedelta(days=1)).isoformat(),
        today.isoformat(),
        (today + timedelta(days=1)).isoformat(),
    ]

    with pytest.raises(ValueError, match="today or a future"):
        therapist_transition_service._parse_transition_dates(values)


def test_locked_past_transition_date_can_remain_during_partial_reschedule() -> None:
    today = today_ist()
    locked = today - timedelta(days=1)
    values = [
        locked.isoformat(),
        (today + timedelta(days=2)).isoformat(),
        (today + timedelta(days=5)).isoformat(),
    ]

    parsed = therapist_transition_service._parse_transition_dates(
        values,
        allowed_past_dates={locked},
    )

    assert parsed == [locked, today + timedelta(days=2), today + timedelta(days=5)]


def test_school_transition_requires_day_type() -> None:
    case = Case(
        case_code="TRANSITION-DAY-TYPE",
        child_id=1,
        service_type="Shadow support",
        product_module="shadow_support",
    )
    with pytest.raises(ValueError, match="Select half day or full day"):
        therapist_transition_service._day_type_value(case)

    case.day_type = CaseDayType.HALF_DAY
    assert therapist_transition_service._day_type_value(case) == "HALF_DAY"


def test_package_payout_adds_transition_pay_without_counting_regular_sessions() -> None:
    case = Case(
        case_code="TRANSITION-PAY",
        child_id=1,
        service_type="Shadow support",
        product_module="shadow_support",
        billing_type=BillingType.PACKAGE,
        package_session_count=20,
        compensation_mode=CompensationMode.FIXED_LUMP,
        therapist_fixed_pay_inr=20_000,
    )
    lines = [
        {
            "included": True,
            "line_type": SessionLineType.INCLUDED.value,
            "amount_inr": 1_000,
            "flags": {},
        },
        {
            "included": True,
            "line_type": SessionLineType.PER_SESSION.value,
            "amount_inr": 500,
            "flags": {"transition_log": True},
        },
    ]

    included, additional, total = invoice_billing_service.compute_case_totals(case, lines)

    assert included == 1
    assert additional == 0
    assert total == 1_500
