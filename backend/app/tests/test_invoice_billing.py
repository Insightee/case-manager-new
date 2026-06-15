from app.models.case import BillingType, Case, CompensationMode
from app.models.invoice_line import SessionLineType
from app.services import invoice_billing_service as billing


def _case_per_session():
    c = Case(
        id=1,
        case_code="T-1",
        child_id=1,
        service_type="Homecare",
        product_module="homecare",
    )
    c.billing_type = BillingType.PER_SESSION
    c.client_rate_per_session_inr = 1000
    c.compensation_mode = CompensationMode.PERCENTAGE
    c.pay_share_pct = 60
    return c


def _case_package_pct():
    c = Case(
        id=2,
        case_code="T-2",
        child_id=1,
        service_type="Homecare",
        product_module="homecare",
    )
    c.billing_type = BillingType.PACKAGE
    c.package_session_count = 20
    c.package_amount_inr = 25000
    c.compensation_mode = CompensationMode.PERCENTAGE
    c.pay_share_pct = 60
    return c


def _case_package_fixed():
    c = _case_package_pct()
    c.compensation_mode = CompensationMode.FIXED_LUMP
    c.therapist_fixed_pay_inr = 25000
    return c


def test_per_session_amount():
    case = _case_per_session()
    assert billing.compute_session_line_amount(case, SessionLineType.PER_SESSION) == 600.0


def test_per_session_fixed_amount():
    case = _case_per_session()
    case.compensation_mode = CompensationMode.FIXED_LUMP
    case.therapist_fixed_pay_inr = 750
    case.pay_share_pct = None
    assert billing.compute_session_line_amount(case, SessionLineType.PER_SESSION) == 750.0


def test_validate_per_session_fixed_lump():
    from app.core.billing_validation import validate_case_billing

    case = _case_per_session()
    case.compensation_mode = CompensationMode.FIXED_LUMP
    case.therapist_fixed_pay_inr = 500
    case.pay_share_pct = None
    validate_case_billing(case)


def test_package_included_and_additional_percentage():
    case = _case_package_pct()
  # per session therapist share: (25000/20)*0.6 = 750
    lines = [
        {"included": True, "line_type": SessionLineType.INCLUDED.value, "amount_inr": 750},
    ] * 20 + [
        {"included": True, "line_type": SessionLineType.ADDITIONAL.value, "amount_inr": 750},
    ] * 2
    included, additional, total = billing.compute_case_totals(case, lines)
    assert included == 20
    assert additional == 2
    assert total == 16500.0


def test_package_extra_fixed_lump():
    case = _case_package_fixed()
    per_extra = 25000 / 20
    lines = [
        {"included": True, "line_type": SessionLineType.INCLUDED.value, "amount_inr": per_extra},
    ] * 20 + [
        {"included": True, "line_type": SessionLineType.ADDITIONAL.value, "amount_inr": per_extra},
    ]
    included, additional, total = billing.compute_case_totals(case, lines)
    assert included == 20
    assert additional == 1
    assert total == 26250.0
