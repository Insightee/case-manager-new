"""Unit tests for session venue defaults and lumpsum billing helpers."""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.core.billing_validation import (
    client_amount_inr,
    needs_low_share_review,
    resolve_therapist_pay,
    validate_case_billing,
)
from app.core.session_defaults import (
    default_service_location_type,
    default_session_mode_for_case,
    is_school_default_module,
)
from app.models.case import BillingType, Case, CompensationMode
from app.models.session import SessionMode


def test_shadow_defaults_to_school():
    assert is_school_default_module("shadow_support")
    assert is_school_default_module("Shadow Support")
    assert is_school_default_module("b2b")
    assert not is_school_default_module("homecare")
    assert default_service_location_type("shadow_support") == "school"
    assert default_service_location_type("homecare") == "home"

    shadow = Case(product_module="shadow_support", service_type="Shadow Support")
    home = Case(product_module="homecare", service_type="Homecare")
    assert default_session_mode_for_case(shadow) == SessionMode.SCHOOL
    assert default_session_mode_for_case(home) == SessionMode.HOME
    assert default_session_mode_for_case(None) == SessionMode.HOME


def test_resolve_therapist_pay_prefers_fixed_then_share():
    case = Case(
        compensation_mode=CompensationMode.FIXED_LUMP,
        therapist_fixed_pay_inr=800,
        pay_share_amount_inr=600,
    )
    assert resolve_therapist_pay(case) == 800.0

    legacy = Case(
        compensation_mode=CompensationMode.PERCENTAGE,
        therapist_fixed_pay_inr=None,
        pay_share_amount_inr=600,
    )
    assert resolve_therapist_pay(legacy) == 600.0
    assert resolve_therapist_pay({"pay_share_amount_inr": 450}) == 450.0


def test_validate_case_billing_locks_lumpsum_and_rejects_over_client():
    case = Case(
        product_module="homecare",
        billing_type=BillingType.PER_SESSION,
        client_rate_per_session_inr=1000,
        pay_share_amount_inr=600,
    )
    validate_case_billing(case)
    assert case.compensation_mode == CompensationMode.FIXED_LUMP
    assert float(case.therapist_fixed_pay_inr) == 600.0
    assert float(case.pay_share_amount_inr) == 600.0

    over = Case(
        product_module="homecare",
        billing_type=BillingType.PER_SESSION,
        client_rate_per_session_inr=1000,
        therapist_fixed_pay_inr=1200,
    )
    with pytest.raises(HTTPException) as exc:
        validate_case_billing(over)
    assert "cannot be more" in str(exc.value.detail).lower()


def test_homecare_low_share_flags_review():
    billing = {
        "product_module": "homecare",
        "billing_type": "PER_SESSION",
        "client_rate_per_session_inr": 1000,
        "therapist_fixed_pay_inr": 150,
    }
    assert client_amount_inr(billing) == 1000.0
    assert needs_low_share_review(billing) is True

    ok = {
        "product_module": "homecare",
        "billing_type": "PER_SESSION",
        "client_rate_per_session_inr": 1000,
        "therapist_fixed_pay_inr": 350,
    }
    assert needs_low_share_review(ok) is False

    shadow = {
        "product_module": "shadow_support",
        "billing_type": "PACKAGE",
        "package_amount_inr": 25000,
        "therapist_fixed_pay_inr": 1000,
    }
    assert needs_low_share_review(shadow) is False
