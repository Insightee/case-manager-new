from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.billing_validation import (
    apply_billing_payload,
    case_billing_dict,
    is_margin_gated_product,
    needs_low_insighte_margin_review,
    resolve_therapist_pay,
)
from app.core.config import settings
from app.models.billing_approval_request import BillingApprovalRequest, BillingApprovalStatus
from app.models.case import BillingType, Case, CompensationMode
from app.models.role import Role
from app.models.user import User
from app.services import notification_service


def _money(value: object) -> Decimal:
    if value in (None, ""):
        return Decimal("0")
    return Decimal(str(value))


def projected_profit_inr(billing: dict) -> Decimal:
    billing_type = billing.get("billing_type")
    if hasattr(billing_type, "value"):
        billing_type = billing_type.value

    if billing_type == BillingType.PER_SESSION.value:
        client_amount = _money(billing.get("client_rate_per_session_inr"))
    elif billing_type == BillingType.PACKAGE.value:
        client_amount = _money(billing.get("package_amount_inr"))
    elif billing_type == BillingType.MONTHLY_FIXED.value:
        client_amount = _money(billing.get("client_monthly_rate_inr"))
    else:
        return Decimal("0")

    therapist_amount = _money(resolve_therapist_pay(billing))
    return (client_amount - therapist_amount).quantize(Decimal("0.01"))


def merged_billing(case: Case, proposed: dict) -> dict:
    merged = case_billing_dict(case)
    merged.pop("billing_updated_at", None)
    merged.update(proposed)
    return merged


def validate_proposed_billing(case: Case, proposed: dict) -> dict:
    merged = merged_billing(case, proposed)
    candidate = Case()
    apply_billing_payload(candidate, merged)
    return merged


def _configured_approver(db: Session) -> User | None:
    email = settings.billing_approval_approver_email.strip().lower()
    approver = db.scalars(
        select(User).where(User.email == email, User.is_active.is_(True))
    ).first()
    if approver or not settings.is_development:
        return approver
    return db.scalars(
        select(User)
        .join(User.roles)
        .where(Role.name == "SUPER_ADMIN", User.is_active.is_(True))
        .order_by(User.id)
    ).first()


def is_designated_approver(db: Session, user: User) -> bool:
    approver = _configured_approver(db)
    return bool(approver and approver.id == user.id)


def requires_approval(billing: dict) -> bool:
    """Product-scoped margin gates.

    Homecare / counselling: Insighte margin below 30% → super-admin review.
    Absolute ₹5k profit floor does **not** apply to those products.

    Shadow (and other modules): keep the absolute ₹5k minimum-profit floor.
    """
    if is_margin_gated_product(billing):
        return needs_low_insighte_margin_review(billing)
    return projected_profit_inr(billing) < Decimal(str(settings.billing_minimum_profit_inr))


def stamp_read(payload: dict, row: BillingApprovalRequest | None) -> dict:
    if not row:
        return payload
    payload["billing_approval_status"] = row.status.value
    payload["billing_approval_request_id"] = row.id
    payload["projected_profit_inr"] = float(row.projected_profit_inr)
    return payload


def apply_or_request(
    db: Session,
    *,
    case: Case,
    proposed: dict | None,
    requester: User,
) -> BillingApprovalRequest | None:
    if not proposed or not any(value is not None for value in proposed.values()):
        return None
    from app.services import billing_rate_history_service

    previous = case_billing_dict(case)
    merged = validate_proposed_billing(case, proposed)
    if requires_approval(merged) and not is_designated_approver(db, requester):
        return request_approval(db, case=case, proposed=proposed, requester=requester)
    apply_billing_payload(case, proposed, requester.id)
    billing_rate_history_service.record_rate_change(
        db,
        case=case,
        previous=previous,
        proposed=proposed,
        changed_by_user_id=requester.id,
    )
    return None


def get_pending_for_case(db: Session, case_id: int) -> BillingApprovalRequest | None:
    return db.scalars(
        select(BillingApprovalRequest).where(
            BillingApprovalRequest.case_id == case_id,
            BillingApprovalRequest.status == BillingApprovalStatus.PENDING,
        )
    ).first()


def request_approval(
    db: Session,
    *,
    case: Case,
    proposed: dict,
    requester: User,
) -> BillingApprovalRequest:
    if get_pending_for_case(db, case.id):
        raise ValueError("A billing approval request is already pending for this case.")
    approver = _configured_approver(db)
    if not approver:
        raise ValueError("The billing approver is not available. Please contact an administrator.")

    merged = validate_proposed_billing(case, proposed)
    profit = projected_profit_inr(merged)
    row = BillingApprovalRequest(
        case_id=case.id,
        previous_billing=case_billing_dict(case),
        proposed_billing=merged,
        projected_profit_inr=profit,
        requested_by_user_id=requester.id,
    )
    db.add(row)
    db.flush()
    notification_service.create_notification(
        db,
        user_id=approver.id,
        title="Low-margin billing needs approval",
        body=f"{case.case_code}: projected Insighte profit is ₹{profit:,.2f}.",
        entity_type="billing_approval_request",
        entity_id=row.id,
        dedupe_key=notification_service.notification_dedupe_key(
            "billing_approval",
            "billing_approval_request",
            row.id,
            BillingApprovalStatus.PENDING.value,
        ),
    )
    return row


def get_request(db: Session, request_id: int) -> BillingApprovalRequest | None:
    return db.get(BillingApprovalRequest, request_id)


def request_to_read(row: BillingApprovalRequest) -> dict:
    return {
        "id": row.id,
        "caseId": row.case_id,
        "caseCode": row.case.case_code if row.case else None,
        "status": row.status.value,
        "previousBilling": row.previous_billing,
        "proposedBilling": row.proposed_billing,
        "projectedProfitInr": float(row.projected_profit_inr),
        "requestedBy": row.requester.full_name if row.requester else None,
        "requestedByUserId": row.requested_by_user_id,
        "reviewedBy": row.reviewer.full_name if row.reviewer else None,
        "reviewedByUserId": row.reviewed_by_user_id,
        "requestedAt": row.requested_at.isoformat() if row.requested_at else None,
        "reviewedAt": row.reviewed_at.isoformat() if row.reviewed_at else None,
        "appliedAt": row.applied_at.isoformat() if row.applied_at else None,
    }


def approve(db: Session, row: BillingApprovalRequest, approver: User) -> Case:
    if row.status != BillingApprovalStatus.PENDING:
        raise ValueError("This billing approval request has already been reviewed.")
    if not is_designated_approver(db, approver):
        raise PermissionError("Only the designated billing approver can approve this request.")
    case = db.get(Case, row.case_id)
    if not case:
        raise ValueError("Case not found.")

    from app.services import billing_rate_history_service

    now = datetime.now(timezone.utc)
    previous = case_billing_dict(case)
    apply_billing_payload(case, row.proposed_billing, approver.id)
    billing_rate_history_service.record_rate_change(
        db,
        case=case,
        previous=previous,
        proposed=row.proposed_billing or {},
        changed_by_user_id=approver.id,
    )
    row.status = BillingApprovalStatus.APPROVED
    row.reviewed_by_user_id = approver.id
    row.reviewed_at = now
    row.applied_at = now
    notification_service.create_notification(
        db,
        user_id=row.requested_by_user_id,
        title="Billing change approved",
        body=f"{case.case_code}: the requested billing is now active.",
        entity_type="billing_approval_request",
        entity_id=row.id,
    )
    db.flush()
    return case


def reject(db: Session, row: BillingApprovalRequest, approver: User) -> None:
    if row.status != BillingApprovalStatus.PENDING:
        raise ValueError("This billing approval request has already been reviewed.")
    if not is_designated_approver(db, approver):
        raise PermissionError("Only the designated billing approver can reject this request.")

    now = datetime.now(timezone.utc)
    row.status = BillingApprovalStatus.REJECTED
    row.reviewed_by_user_id = approver.id
    row.reviewed_at = now
    case = db.get(Case, row.case_id)
    notification_service.create_notification(
        db,
        user_id=row.requested_by_user_id,
        title="Billing change not approved",
        body=f"{case.case_code if case else 'Case'}: the current billing remains active.",
        entity_type="billing_approval_request",
        entity_id=row.id,
    )
    db.flush()
