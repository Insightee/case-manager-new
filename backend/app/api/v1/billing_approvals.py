from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_request_meta
from app.core.audit import log_audit
from app.core.database import get_db
from app.core.permissions import user_has_permission
from app.models.billing_approval_request import BillingApprovalRequest, BillingApprovalStatus
from app.models.case import Case
from app.models.user import User
from app.services import billing_approval_service


router = APIRouter(prefix="/billing-approvals", tags=["billing approvals"])


def _can_list_billing_approvals(db: Session, user: User) -> bool:
    return bool(
        billing_approval_service.is_designated_approver(db, user)
        or user_has_permission(user, "case.read.all")
        or user_has_permission(user, "case.read.team")
        or user_has_permission(user, "admin.override")
    )


def _list_item(row: BillingApprovalRequest, case_code: str | None, requester_name: str | None) -> dict:
    """Staff list shape. Omits billing payloads, which can carry account notes."""
    return {
        "id": row.id,
        "case_id": row.case_id,
        "case_code": case_code,
        "status": row.status.value,
        "requested_at": row.requested_at.isoformat() if row.requested_at else None,
        "reviewed_at": row.reviewed_at.isoformat() if row.reviewed_at else None,
        "requested_by_name": requester_name,
        "projected_profit_inr": float(row.projected_profit_inr),
    }


@router.get("")
def list_billing_approvals(
    status: str | None = Query(None, description="PENDING, APPROVED, or REJECTED"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Read-only staff list of billing-change approval requests."""
    if not _can_list_billing_approvals(db, user):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    stmt = select(BillingApprovalRequest).order_by(BillingApprovalRequest.requested_at.desc())
    if status:
        try:
            wanted = BillingApprovalStatus(status.strip().upper())
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Looks like we still need a valid approval status before we can list these.",
            ) from None
        stmt = stmt.where(BillingApprovalRequest.status == wanted)
    rows = db.scalars(stmt).all()
    case_ids = {row.case_id for row in rows}
    requester_ids = {row.requested_by_user_id for row in rows}
    case_codes = {}
    if case_ids:
        case_codes = dict(db.execute(select(Case.id, Case.case_code).where(Case.id.in_(case_ids))).all())
    requester_names = {}
    if requester_ids:
        requester_names = dict(
            db.execute(select(User.id, User.full_name).where(User.id.in_(requester_ids))).all()
        )
    return {
        "items": [
            _list_item(row, case_codes.get(row.case_id), requester_names.get(row.requested_by_user_id))
            for row in rows
        ],
        "total": len(rows),
    }


def _get_visible_request(db: Session, request_id: int, user: User):
    row = billing_approval_service.get_request(db, request_id)
    if not row:
        raise HTTPException(status_code=404, detail="Billing approval request not found.")
    if (
        row.requested_by_user_id != user.id
        and not billing_approval_service.is_designated_approver(db, user)
    ):
        raise HTTPException(status_code=403, detail="Billing approval access denied.")
    return row


@router.get("/{request_id}")
def get_billing_approval(
    request_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    result = billing_approval_service.request_to_read(_get_visible_request(db, request_id, user))
    result["canReview"] = billing_approval_service.is_designated_approver(db, user)
    return result


@router.post("/{request_id}/approve")
def approve_billing(
    request_id: int,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = _get_visible_request(db, request_id, user)
    try:
        case = billing_approval_service.approve(db, row, user)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    log_audit(
        db,
        actor_user_id=user.id,
        action="approve_low_margin_billing",
        entity_type="billing_approval_request",
        entity_id=row.id,
        case_id=case.id,
        old_value=row.previous_billing,
        new_value={
            "applied_billing": row.proposed_billing,
            "projected_profit_inr": float(row.projected_profit_inr),
            "applied_at": row.applied_at,
        },
        **get_request_meta(request),
    )
    db.commit()
    db.refresh(row)
    return billing_approval_service.request_to_read(row)


@router.post("/{request_id}/reject")
def reject_billing(
    request_id: int,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = _get_visible_request(db, request_id, user)
    try:
        billing_approval_service.reject(db, row, user)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    log_audit(
        db,
        actor_user_id=user.id,
        action="reject_low_margin_billing",
        entity_type="billing_approval_request",
        entity_id=row.id,
        case_id=row.case_id,
        old_value={"status": "PENDING"},
        new_value={"status": row.status.value},
        **get_request_meta(request),
    )
    db.commit()
    db.refresh(row)
    return billing_approval_service.request_to_read(row)
