from app.core.billing_month import (
    parse_billing_month,
    therapist_invoice_month_keys,
    try_parse_billing_month,
)


def test_parse_aliases_and_iso():
    assert parse_billing_month("2026-10") == "2026-10"
    assert parse_billing_month("Oct 2026") == "2026-10"
    assert parse_billing_month("October 2026") == "2026-10"
    assert try_parse_billing_month("not-a-month") is None
    assert try_parse_billing_month("") is None


def test_therapist_invoice_month_keys_keep_aliases():
    keys = therapist_invoice_month_keys("2026-05")
    assert "2026-05" in keys
    assert "May 2026" in keys
    assert "May 2026" in keys or any(k.startswith("May") for k in keys)
