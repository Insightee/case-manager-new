from app.models.case import BillingType, Case, CompensationMode
from app.models.invoice_line import SessionLineType
from app.services import invoice_billing_service as billing
from app.services.finance_payout_preview_service import CycleSegment


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
    c.pay_share_amount_inr = 600
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
    c.pay_share_amount_inr = 15000
    return c


def _case_package_fixed():
    c = _case_package_pct()
    c.compensation_mode = CompensationMode.FIXED_LUMP
    c.therapist_fixed_pay_inr = 25000
    return c


def test_per_session_amount():
    case = _case_per_session()
    assert billing.compute_session_line_amount(case, SessionLineType.PER_SESSION) == 600.0


def test_monthly_fixed_line_amount_without_package_count():
    """Monthly cases must not require a package size to price a session line."""
    case = Case(
        id=3,
        case_code="T-3",
        child_id=1,
        service_type="Homecare",
        product_module="homecare",
    )
    case.billing_type = BillingType.MONTHLY_FIXED
    case.package_session_count = None
    case.compensation_mode = CompensationMode.FIXED_LUMP
    case.therapist_fixed_pay_inr = 18000
    case.client_monthly_rate_inr = 25000
    assert billing.compute_session_line_amount(case, SessionLineType.INCLUDED) == 0.0
    lines = [
        {"included": True, "line_type": SessionLineType.INCLUDED.value, "amount_inr": 0, "flags": {}},
    ]
    _, _, total = billing.compute_case_totals(case, lines)
    assert total == 18000.0


def test_monthly_fixed_shadow_line_uses_day_rate():
    from app.services.finance_payout_preview_service import SHADOW_MONTHLY_DAYS

    case = Case(
        id=4,
        case_code="T-4",
        child_id=1,
        service_type="Shadow",
        product_module="shadow_support",
    )
    case.billing_type = BillingType.MONTHLY_FIXED
    case.package_session_count = None
    case.compensation_mode = CompensationMode.FIXED_LUMP
    case.therapist_fixed_pay_inr = 18000
    amount = billing.compute_session_line_amount(case, SessionLineType.INCLUDED)
    assert amount == round(18000 / SHADOW_MONTHLY_DAYS, 2)


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


def test_engine_case_gross_homecare_uses_approved_sessions_times_share():
    case = _case_per_session()
    lines = [
        {"included": True, "line_type": SessionLineType.PER_SESSION.value, "amount_inr": 600, "flags": {}},
    ] * 5
    included, additional, total = billing.engine_case_gross(case, lines, segment=None)
    assert total == 3000.0


def test_engine_case_gross_shadow_uses_cycle_days_plus_transition():
    case = Case(
        id=9,
        case_code="T-SHADOW",
        child_id=1,
        service_type="Shadow support",
        product_module="shadow_support",
    )
    case.billing_type = BillingType.PACKAGE
    case.compensation_mode = CompensationMode.PERCENTAGE
    case.package_amount_inr = 30000
    case.pay_share_amount_inr = 18000
    lines = [
        {"included": True, "line_type": SessionLineType.INCLUDED.value, "amount_inr": 1000, "flags": {}},
    ] * 8
    segment = CycleSegment(
        therapist_user_id=1,
        approved_sessions=8,
        approved_absence=0,
        hours=0.0,
        calendar_days=10,
        unpaid_leaves=0,
        paid_leaves=0,
        leave_credits=0,
        transition_days=1,
        transition_day_type="HALF_DAY",
        transition_total=500.0,
        therapist_start_date=None,
        case_start_date=None,
        case_end_date=None,
        first_log=None,
        last_log=None,
        is_incoming_replacement=False,
        is_outgoing_replacement=True,
    )
    included, additional, total = billing.engine_case_gross(case, lines, segment=segment)
    assert included == 8
    assert total == round((18000 / 30) * 10 + 500, 2)
