from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException

from app.models.case import BillingType, Case, ClientBillingMode, CompensationMode

# Homecare therapist share below this fraction of client amount is routed to review.
HOMECARE_LOW_SHARE_RATIO = 0.20
# Soft guidance floor (target band is 30–40% therapist share of client).
HOMECARE_GUIDANCE_SHARE_RATIO = 0.30
# Insighte margin (client − therapist) / client — flag finance report rows below this.
INSIGHTE_LOW_MARGIN_RATIO = 0.30


def margin_pct_and_flag(*, client_total_inr: float, therapist_total_inr: float) -> dict:
    """Insighte margin % and low-margin flag for finance margin-by-case reports."""
    client = float(client_total_inr or 0)
    therapist = float(therapist_total_inr or 0)
    margin_inr = round(client - therapist, 2)
    if client <= 0:
        return {
            "marginInr": margin_inr,
            "marginPct": None,
            "lowMargin": False,
            "marginFlag": "NO_CLIENT_TOTAL",
        }
    margin_pct = round((margin_inr / client) * 100, 2)
    low = margin_pct < (INSIGHTE_LOW_MARGIN_RATIO * 100)
    return {
        "marginInr": margin_inr,
        "marginPct": margin_pct,
        "lowMargin": low,
        "marginFlag": "LOW_MARGIN_BELOW_30" if low else "",
    }


def resolve_therapist_pay(case: Case | dict | None) -> float:
    """Single INR therapist pay: prefer fixed lump, fall back to legacy share amount.

    Both columns store rupees (the old pay_share_pct column was converted and dropped).
    """
    if case is None:
        return 0.0
    if isinstance(case, dict):
        fixed = case.get("therapist_fixed_pay_inr")
        share = case.get("pay_share_amount_inr")
    else:
        fixed = getattr(case, "therapist_fixed_pay_inr", None)
        share = getattr(case, "pay_share_amount_inr", None)
    if fixed is not None and float(fixed) > 0:
        return float(fixed)
    if share is not None and float(share) > 0:
        return float(share)
    return 0.0


def client_amount_inr(case: Case | dict | None) -> float:
    """Configured client charge matching billing_type."""
    if case is None:
        return 0.0
    if isinstance(case, dict):
        billing_type = case.get("billing_type")
        if hasattr(billing_type, "value"):
            billing_type = billing_type.value
        rate = case.get("client_rate_per_session_inr")
        monthly = case.get("client_monthly_rate_inr")
        package = case.get("package_amount_inr")
    else:
        billing_type = case.billing_type.value if case.billing_type else None
        rate = case.client_rate_per_session_inr
        monthly = case.client_monthly_rate_inr
        package = case.package_amount_inr
    if billing_type == BillingType.PER_SESSION.value or billing_type == BillingType.PER_SESSION:
        return float(rate or 0)
    if billing_type == BillingType.MONTHLY_FIXED.value or billing_type == BillingType.MONTHLY_FIXED:
        return float(monthly or package or 0)
    if billing_type == BillingType.PACKAGE.value or billing_type == BillingType.PACKAGE:
        return float(package or 0)
    return float(package or monthly or rate or 0)


def is_homecare_product(case: Case | dict | None) -> bool:
    if case is None:
        return False
    if isinstance(case, dict):
        mod = (case.get("product_module") or "") or ""
        service = (case.get("service_type") or "") or ""
    else:
        mod = (case.product_module or "") if case else ""
        service = (case.service_type or "") if case else ""
    token = f"{mod} {service}".lower()
    return "homecare" in token or "home care" in token


def therapist_share_ratio(case: Case | dict | None) -> float | None:
    """Therapist pay / client amount. None when client amount is missing/zero."""
    client = client_amount_inr(case)
    if client <= 0:
        return None
    return resolve_therapist_pay(case) / client


def needs_low_share_review(case: Case | dict | None) -> bool:
    """Homecare share under 20% of client amount should go to the review queue."""
    if not is_homecare_product(case):
        return False
    ratio = therapist_share_ratio(case)
    if ratio is None:
        return False
    return ratio < HOMECARE_LOW_SHARE_RATIO


def _require_compensation(case: Case, *, context: str) -> None:
    """Lock therapist pay to FIXED_LUMP with a single INR amount."""
    # Prefer an existing share amount when fixed is empty (legacy PERCENTAGE rows).
    if (not case.therapist_fixed_pay_inr or float(case.therapist_fixed_pay_inr) <= 0) and (
        case.pay_share_amount_inr and float(case.pay_share_amount_inr) > 0
    ):
        case.therapist_fixed_pay_inr = case.pay_share_amount_inr

    case.compensation_mode = CompensationMode.FIXED_LUMP

    if not case.therapist_fixed_pay_inr or float(case.therapist_fixed_pay_inr) <= 0:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Looks like we still need the therapist pay (lumpsum, INR) "
                f"for this {context} case before we can save."
            ),
        )

    # Keep share column in sync so legacy readers that still check it stay correct.
    case.pay_share_amount_inr = case.therapist_fixed_pay_inr

    client = client_amount_inr(case)
    pay = float(case.therapist_fixed_pay_inr)
    if client > 0 and pay > client:
        raise HTTPException(
            status_code=400,
            detail=(
                "Therapist pay cannot be more than the client billing amount. "
                "Please adjust the lumpsum so it stays within the family charge."
            ),
        )


def validate_case_billing(case: Case) -> None:
    if not case.billing_type:
        return

    if case.billing_type == BillingType.MONTHLY_FIXED:
        if case.client_rate_per_session_inr is not None and float(case.client_rate_per_session_inr) > 0:
            raise HTTPException(
                status_code=400,
                detail=(
                    "A monthly case cannot have a per-session rate — "
                    "enter the monthly rate instead."
                ),
            )
        if not case.client_monthly_rate_inr or float(case.client_monthly_rate_inr) <= 0:
            raise HTTPException(
                status_code=400,
                detail="Please enter the monthly client rate in rupees before saving.",
            )
        _require_compensation(case, context="monthly")
        return

    if case.billing_type == BillingType.PER_SESSION:
        if case.client_monthly_rate_inr is not None and float(case.client_monthly_rate_inr) > 0:
            raise HTTPException(
                status_code=400,
                detail=(
                    "A per-session case cannot have a monthly rate — "
                    "enter the per-session rate instead."
                ),
            )
        if not case.client_rate_per_session_inr or case.client_rate_per_session_inr <= 0:
            raise HTTPException(
                status_code=400,
                detail="Please enter the client rate per session in rupees before saving.",
            )
        _require_compensation(case, context="per-session")
        return

    if case.billing_type == BillingType.PACKAGE:
        if not case.package_session_count or case.package_session_count <= 0:
            raise HTTPException(
                status_code=400,
                detail="Please enter how many sessions are in this package before saving.",
            )
        if not case.package_amount_inr or case.package_amount_inr <= 0:
            raise HTTPException(
                status_code=400,
                detail="Please enter the package amount in rupees before saving.",
            )
        _require_compensation(case, context="package")


def apply_billing_payload(case: Case, data: dict, user_id: int | None = None) -> None:
    billing_keys = {
        "product_billing_rule_id",
        "client_billing_mode",
        "billing_type",
        "client_rate_per_session_inr",
        "client_monthly_rate_inr",
        "package_session_count",
        "package_amount_inr",
        "compensation_mode",
        "pay_share_amount_inr",
        "therapist_fixed_pay_inr",
        "billing_notes",
    }
    if not any(k in data for k in billing_keys):
        return
    for k, v in data.items():
        if k in billing_keys and v is not None:
            if k in ("billing_type", "compensation_mode", "client_billing_mode") and isinstance(v, str):
                if k == "billing_type":
                    setattr(case, k, BillingType(v))
                elif k == "compensation_mode":
                    # Incoming PERCENTAGE is coerced to FIXED_LUMP; amount columns carry INR.
                    mode = CompensationMode(v) if v in ("PERCENTAGE", "FIXED_LUMP") else CompensationMode.FIXED_LUMP
                    if mode == CompensationMode.PERCENTAGE:
                        mode = CompensationMode.FIXED_LUMP
                    setattr(case, k, mode)
                else:
                    setattr(case, k, ClientBillingMode(v))
            else:
                setattr(case, k, v)
    # Explicit nulls: allow clearing the wrong-rate field when switching billing type.
    if "client_rate_per_session_inr" in data and data["client_rate_per_session_inr"] is None:
        case.client_rate_per_session_inr = None
    if "client_monthly_rate_inr" in data and data["client_monthly_rate_inr"] is None:
        case.client_monthly_rate_inr = None

    # Promote posted INR into therapist_fixed_pay_inr (canonical lumpsum column).
    # Prefer an explicit therapist_fixed_pay_inr; otherwise adopt pay_share_amount_inr
    # even when an older fixed value already exists (legacy PERCENTAGE writers).
    posted_fixed = data.get("therapist_fixed_pay_inr")
    posted_share = data.get("pay_share_amount_inr")
    if posted_fixed not in (None, "") and float(posted_fixed or 0) > 0:
        case.therapist_fixed_pay_inr = float(posted_fixed)
    elif posted_share not in (None, "") and float(posted_share or 0) > 0:
        case.therapist_fixed_pay_inr = float(posted_share)

    case.billing_updated_at = datetime.now(timezone.utc)
    if user_id:
        case.billing_updated_by_user_id = user_id
    validate_case_billing(case)


def case_billing_dict(case: Case) -> dict:
    return {
        "product_billing_rule_id": case.product_billing_rule_id,
        "billing_type": case.billing_type.value if case.billing_type else None,
        "client_rate_per_session_inr": (
            float(case.client_rate_per_session_inr) if case.client_rate_per_session_inr else None
        ),
        "client_monthly_rate_inr": (
            float(case.client_monthly_rate_inr) if case.client_monthly_rate_inr else None
        ),
        "package_session_count": case.package_session_count,
        "package_amount_inr": float(case.package_amount_inr) if case.package_amount_inr else None,
        "compensation_mode": case.compensation_mode.value if case.compensation_mode else None,
        "pay_share_amount_inr": float(case.pay_share_amount_inr) if case.pay_share_amount_inr else None,
        "therapist_fixed_pay_inr": (
            float(case.therapist_fixed_pay_inr) if case.therapist_fixed_pay_inr else None
        ),
        "billing_notes": case.billing_notes,
        "client_billing_mode": case.client_billing_mode.value if case.client_billing_mode else None,
        "product_module": case.product_module,
        "service_type": case.service_type,
        "billing_updated_at": case.billing_updated_at.isoformat() if case.billing_updated_at else None,
        "therapist_pay_inr": resolve_therapist_pay(case) or None,
    }
