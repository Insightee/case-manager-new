from __future__ import annotations

from fastapi import HTTPException

from app.models.case import BillingType, Case, ClientBillingMode, CompensationMode


def validate_case_billing(case: Case) -> None:
    if not case.billing_type:
        return
    if case.billing_type == BillingType.PER_SESSION:
        if not case.client_rate_per_session_inr or case.client_rate_per_session_inr <= 0:
            raise HTTPException(status_code=400, detail="client_rate_per_session_inr required for PER_SESSION billing")
        if case.compensation_mode != CompensationMode.PERCENTAGE:
            raise HTTPException(status_code=400, detail="PER_SESSION billing requires PERCENTAGE compensation")
        if not case.pay_share_pct or case.pay_share_pct < 50 or case.pay_share_pct > 70:
            raise HTTPException(status_code=400, detail="pay_share_pct must be between 50 and 70")
    elif case.billing_type == BillingType.PACKAGE:
        if not case.package_session_count or case.package_session_count <= 0:
            raise HTTPException(status_code=400, detail="package_session_count required for PACKAGE billing")
        if not case.package_amount_inr or case.package_amount_inr <= 0:
            raise HTTPException(status_code=400, detail="package_amount_inr required for PACKAGE billing")
        if not case.compensation_mode:
            raise HTTPException(status_code=400, detail="compensation_mode required for PACKAGE billing")
        if case.compensation_mode == CompensationMode.PERCENTAGE:
            if not case.pay_share_pct or case.pay_share_pct < 50 or case.pay_share_pct > 70:
                raise HTTPException(status_code=400, detail="pay_share_pct must be between 50 and 70")
        elif case.compensation_mode == CompensationMode.FIXED_LUMP:
            if not case.therapist_fixed_pay_inr or case.therapist_fixed_pay_inr <= 0:
                raise HTTPException(status_code=400, detail="therapist_fixed_pay_inr required for FIXED_LUMP compensation")


def apply_billing_payload(case: Case, data: dict, user_id: int | None = None) -> None:
    from datetime import datetime, timezone

    billing_keys = {
        "client_billing_mode",
        "billing_type",
        "client_rate_per_session_inr",
        "package_session_count",
        "package_amount_inr",
        "compensation_mode",
        "pay_share_pct",
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
    case.billing_updated_at = datetime.now(timezone.utc)
    if user_id:
        case.billing_updated_by_user_id = user_id
    validate_case_billing(case)


def case_billing_dict(case: Case) -> dict:
    return {
        "billing_type": case.billing_type.value if case.billing_type else None,
        "client_rate_per_session_inr": float(case.client_rate_per_session_inr) if case.client_rate_per_session_inr else None,
        "package_session_count": case.package_session_count,
        "package_amount_inr": float(case.package_amount_inr) if case.package_amount_inr else None,
        "compensation_mode": case.compensation_mode.value if case.compensation_mode else None,
        "pay_share_pct": float(case.pay_share_pct) if case.pay_share_pct else None,
        "therapist_fixed_pay_inr": float(case.therapist_fixed_pay_inr) if case.therapist_fixed_pay_inr else None,
        "billing_notes": case.billing_notes,
        "client_billing_mode": case.client_billing_mode.value if case.client_billing_mode else None,
        "billing_updated_at": case.billing_updated_at.isoformat() if case.billing_updated_at else None,
    }
