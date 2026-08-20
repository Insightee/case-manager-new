from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException

from app.models.case import BillingType, Case, ClientBillingMode, CompensationMode


def _require_compensation(case: Case, *, context: str) -> None:
    if not case.compensation_mode:
        if case.billing_type == BillingType.PER_SESSION:
            case.compensation_mode = CompensationMode.PERCENTAGE
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Please choose how the therapist is paid for this {context} case.",
            )
    if case.compensation_mode == CompensationMode.PERCENTAGE:
        if not case.pay_share_amount_inr or case.pay_share_amount_inr <= 0:
            raise HTTPException(
                status_code=400,
                detail="Please enter the therapist pay share in rupees before saving.",
            )
    elif case.compensation_mode == CompensationMode.FIXED_LUMP:
        if not case.therapist_fixed_pay_inr or case.therapist_fixed_pay_inr <= 0:
            raise HTTPException(
                status_code=400,
                detail="Please enter the therapist fixed pay in rupees before saving.",
            )
    else:
        raise HTTPException(
            status_code=400,
            detail="Therapist pay must be either a share amount or a fixed lump sum.",
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
                    setattr(case, k, CompensationMode(v))
                else:
                    setattr(case, k, ClientBillingMode(v))
            else:
                setattr(case, k, v)
    # Explicit nulls: allow clearing the wrong-rate field when switching billing type.
    if "client_rate_per_session_inr" in data and data["client_rate_per_session_inr"] is None:
        case.client_rate_per_session_inr = None
    if "client_monthly_rate_inr" in data and data["client_monthly_rate_inr"] is None:
        case.client_monthly_rate_inr = None
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
    }
