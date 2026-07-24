"""Finance therapist payout preview — case-level monthly payout projection."""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models.case import BillingType, Case, CompensationMode
from app.models.user import User
from app.services import leave_policy_service
from app.services.operational_reports_service import (
    _build_billable_metrics,
    _session_hours_by_case,
)
from app.services.reports_export_helpers import (
    MAX_EXPORT_ROWS,
    active_assignment,
    assignment_therapist,
    export_case_id,
    export_therapist_id,
    is_shadow_case,
    leave_days_in_month,
    month_bounds,
    month_long_label,
    scoped_cases,
    user_display_name,
)
from app.services import case_service

SHADOW_MONTHLY_DAYS = 30


def therapist_share_inr(case: Case) -> float:
    """Monthly or per-session therapist share configured on the case."""
    if case.compensation_mode == CompensationMode.FIXED_LUMP:
        return float(case.therapist_fixed_pay_inr or 0)
    return float(case.pay_share_amount_inr or 0)


def client_lumpsum_inr(case: Case) -> float | None:
    """Parent/client charge lump where applicable (package or shadow monthly)."""
    if case.billing_type == BillingType.PACKAGE and case.package_amount_inr:
        return float(case.package_amount_inr)
    if is_shadow_case(case) and case.package_amount_inr:
        return float(case.package_amount_inr)
    return None


def per_session_share_inr(case: Case) -> float:
    share = therapist_share_inr(case)
    if share <= 0:
        return 0.0

    if is_shadow_case(case):
        return round(share / SHADOW_MONTHLY_DAYS, 2)

    if case.billing_type == BillingType.PER_SESSION:
        return round(share, 2)

    pkg_count = int(case.package_session_count or 0)
    if pkg_count <= 0:
        return 0.0
    return round(share / pkg_count, 2)


def predicted_subtotal_inr(
    case: Case,
    *,
    approved_sessions: int,
    unpaid_leaves: int,
) -> float:
    rate = per_session_share_inr(case)
    if rate <= 0:
        return 0.0

    if is_shadow_case(case):
        payable_days = max(SHADOW_MONTHLY_DAYS - unpaid_leaves, 0)
        return round(rate * payable_days, 2)

    return round(rate * approved_sessions, 2)


def payout_preview_row(
    case: Case,
    *,
    ym: str,
    therapist: User,
    metrics: dict[str, Any],
    hours: float,
    leave: dict[str, int],
    leave_credits: int,
) -> dict[str, Any]:
    share = therapist_share_inr(case)
    lumpsum = client_lumpsum_inr(case)
    per_sess = per_session_share_inr(case)
    approved = int(metrics.get("approved_sessions", 0))
    unpaid = int(leave.get("unpaid", 0))
    subtotal = predicted_subtotal_inr(
        case,
        approved_sessions=approved,
        unpaid_leaves=unpaid,
    )

    return {
        "Month": month_long_label(ym),
        "Case ID": export_case_id(case),
        "Client Name": case_service.case_child_display_name(case) or "",
        "Therapist Name": user_display_name(therapist),
        "Therapist ID": export_therapist_id(therapist),
        "Service Type": case.service_type or case.product_module or "",
        "Approved Sessions": approved,
        "Approved Absence": int(metrics.get("approved_child_absence", 0)),
        "Paid Leaves": int(leave.get("paid", 0)),
        "Unpaid Leaves": unpaid,
        "Leave Credits": leave_credits,
        "Total Hours": round(hours, 2),
        "Billable Sessions": int(metrics.get("billable_sessions", 0)),
        "Lumpsum Amount": lumpsum if lumpsum is not None else "",
        "Therapist Share": round(share, 2) if share else "",
        "Per Session Share": per_sess if per_sess else "",
        "Predicted Subtotal": subtotal if subtotal else "",
    }


def payout_preview_rows(
    db: Session,
    ym: str,
    *,
    user: User | None = None,
    product_module: str | None = None,
) -> list[dict[str, Any]]:
    start, end = month_bounds(ym)
    year = int(ym.split("-")[0])

    cases = scoped_cases(db, user, product_module=product_module, active_only=True)
    case_ids = [c.id for c in cases]
    if not case_ids:
        return []

    billable_metrics = _build_billable_metrics(db, cases, case_ids, start, end)
    hours_by_case = _session_hours_by_case(db, case_ids, ym)

    rows: list[dict[str, Any]] = []
    for case in cases[:MAX_EXPORT_ROWS]:
        assign = active_assignment(db, case.id)
        therapist = assignment_therapist(db, assign)
        if not therapist:
            continue

        leave = leave_days_in_month(db, therapist.id, ym)
        balance = leave_policy_service.get_leave_balance(db, therapist, year=year, as_of=end)
        leave_credits = int(
            balance.get("leave_credit_pending", balance.get("paid_remaining", 0)) or 0
        )
        metrics = billable_metrics.get(case.id, {})

        rows.append(
            payout_preview_row(
                case,
                ym=ym,
                therapist=therapist,
                metrics=metrics,
                hours=float(hours_by_case.get(case.id, 0)),
                leave=leave,
                leave_credits=leave_credits,
            )
        )

    return rows
