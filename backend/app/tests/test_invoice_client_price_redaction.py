"""Therapists must never see client-side money.

The payout calculator is the single source of the therapist-share numbers and
is left untouched; client pricing is stripped from therapist-facing
preview/breakdown payloads at the API boundary. These pure-unit tests pin that
redaction: client keys drop, therapist keys survive.
"""

from app.api.v1.invoices import (
    _CLIENT_PRICE_KEYS,
    _redact_billing,
    _redact_breakdown_client_pricing,
    _redact_preview_client_pricing,
)
from app.core.billing_validation import case_billing_dict
from app.models.case import BillingType, Case, CompensationMode

_CLIENT_KEYS = {
    "client_rate_per_session_inr",
    "client_monthly_rate_inr",
    "package_amount_inr",
    "client_billing_mode",
}
_THERAPIST_KEYS = {
    "billing_type",
    "package_session_count",
    "compensation_mode",
    "pay_share_amount_inr",
    "therapist_fixed_pay_inr",
}


def _package_case() -> Case:
    c = Case(id=1, case_code="T-1", child_id=1, service_type="Homecare", product_module="homecare")
    c.billing_type = BillingType.PACKAGE
    c.package_session_count = 20
    c.package_amount_inr = 25000
    c.client_rate_per_session_inr = 1250
    c.compensation_mode = CompensationMode.PERCENTAGE
    c.pay_share_amount_inr = 15000
    return c


def test_redact_billing_drops_client_keys_keeps_therapist_share():
    billing = case_billing_dict(_package_case())
    # Sanity: the raw dict does carry client money before redaction.
    assert billing["client_rate_per_session_inr"] == 1250.0
    assert billing["package_amount_inr"] == 25000.0

    redacted = _redact_billing(billing)

    assert _CLIENT_KEYS.isdisjoint(redacted), "client-side money leaked to therapist"
    assert redacted["pay_share_amount_inr"] == 15000.0
    assert redacted["package_session_count"] == 20
    assert redacted["billing_type"] == "PACKAGE"
    # Original dict is not mutated (admin path still gets full figures).
    assert billing["package_amount_inr"] == 25000.0


def test_client_price_keys_constant_matches_expected_bucket():
    assert set(_CLIENT_PRICE_KEYS) == _CLIENT_KEYS


def test_redact_preview_strips_each_case_group():
    preview = {
        "case_groups": [
            {"case_id": 1, "therapist_share_inr": 900, "billing": case_billing_dict(_package_case())},
            {"case_id": 2, "billing": None},
        ]
    }

    out = _redact_preview_client_pricing(preview)

    group = out["case_groups"][0]
    assert _CLIENT_KEYS.isdisjoint(group["billing"])
    assert group["billing"]["pay_share_amount_inr"] == 15000.0
    assert group["therapist_share_inr"] == 900  # non-billing fields untouched


def test_redact_preview_strips_cases_key_from_build_month_preview():
    # build_month_preview returns groups under "cases" (not "case_groups"); the
    # redactor must strip that shape or the generate/preview drawer leaks pricing.
    preview = {
        "cases": [
            {"case_id": 1, "therapist_share_inr": 600, "billing": case_billing_dict(_package_case())},
        ]
    }

    out = _redact_preview_client_pricing(preview)

    billing = out["cases"][0]["billing"]
    assert _CLIENT_KEYS.isdisjoint(billing), "client-side money leaked via preview 'cases' key"
    assert billing["pay_share_amount_inr"] == 15000.0
    assert out["cases"][0]["therapist_share_inr"] == 600


def test_redact_breakdown_strips_billing_snapshot():
    data = {
        "cases": [
            {"case_id": 1, "therapist_share_inr": 900.0, "billing_snapshot": case_billing_dict(_package_case())},
        ]
    }

    out = _redact_breakdown_client_pricing(data)

    snap = out["cases"][0]["billing_snapshot"]
    assert _CLIENT_KEYS.isdisjoint(snap)
    assert _THERAPIST_KEYS.issubset(snap.keys())
    assert out["cases"][0]["therapist_share_inr"] == 900.0


def test_redact_breakdown_strips_preview_branch_billing_key():
    # Preview-derived breakdowns (from_preview=True) carry billing under "billing",
    # not "billing_snapshot". The therapist UI reads either key, so redaction must
    # cover both or client pricing leaks on preview-only invoices.
    data = {
        "from_preview": True,
        "cases": [
            {"case_id": 1, "therapist_share_inr": 600.0, "billing": case_billing_dict(_package_case())},
        ],
    }

    out = _redact_breakdown_client_pricing(data)

    billing = out["cases"][0]["billing"]
    assert _CLIENT_KEYS.isdisjoint(billing), "client-side money leaked via preview branch"
    assert _THERAPIST_KEYS.issubset(billing.keys())
    assert out["cases"][0]["therapist_share_inr"] == 600.0
