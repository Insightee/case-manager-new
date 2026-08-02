"""Monthly billing first-class rate field + write-path guard."""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.core.billing_validation import apply_billing_payload, validate_case_billing
from app.models.case import BillingType, Case, CompensationMode


def _monthly_case(**kwargs) -> Case:
    case = Case(
        id=101,
        case_code="T-MONTHLY",
        child_id=1,
        service_type="Shadow support",
        product_module="shadow_support",
    )
    case.billing_type = BillingType.MONTHLY_FIXED
    case.client_monthly_rate_inr = 30000.0
    case.client_rate_per_session_inr = None
    case.compensation_mode = CompensationMode.PERCENTAGE
    case.pay_share_amount_inr = 20000.0
    for k, v in kwargs.items():
        setattr(case, k, v)
    return case


def _per_session_case(**kwargs) -> Case:
    case = Case(
        id=102,
        case_code="T-SESSION",
        child_id=1,
        service_type="Homecare",
        product_module="homecare",
    )
    case.billing_type = BillingType.PER_SESSION
    case.client_rate_per_session_inr = 1500.0
    case.client_monthly_rate_inr = None
    case.compensation_mode = CompensationMode.PERCENTAGE
    case.pay_share_amount_inr = 900.0
    for k, v in kwargs.items():
        setattr(case, k, v)
    return case


def test_validate_monthly_rejects_per_session_rate():
    case = _monthly_case(client_rate_per_session_inr=30000.0)
    with pytest.raises(HTTPException) as excinfo:
        validate_case_billing(case)
    assert excinfo.value.status_code == 400
    assert "monthly case cannot have a per-session rate" in excinfo.value.detail


def test_validate_monthly_requires_monthly_rate():
    case = _monthly_case(client_monthly_rate_inr=None)
    with pytest.raises(HTTPException) as excinfo:
        validate_case_billing(case)
    assert "monthly client rate" in excinfo.value.detail


def test_validate_per_session_rejects_monthly_rate():
    case = _per_session_case(client_monthly_rate_inr=30000.0)
    with pytest.raises(HTTPException) as excinfo:
        validate_case_billing(case)
    assert "per-session case cannot have a monthly rate" in excinfo.value.detail


def test_validate_monthly_accepts_clean_payload():
    validate_case_billing(_monthly_case())


def test_apply_billing_payload_clears_wrong_rate_on_monthly():
    case = _per_session_case()
    apply_billing_payload(
        case,
        {
            "billing_type": "MONTHLY_FIXED",
            "client_monthly_rate_inr": 28000.0,
            "client_rate_per_session_inr": None,
            "compensation_mode": "PERCENTAGE",
            "pay_share_amount_inr": 18000.0,
        },
    )
    assert case.billing_type == BillingType.MONTHLY_FIXED
    assert float(case.client_monthly_rate_inr) == 28000.0
    assert case.client_rate_per_session_inr is None
