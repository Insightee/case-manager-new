from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_request_meta
from app.core.audit import log_audit
from app.core.database import get_db
from app.models.user import User
from app.services import billing_approval_service


router = APIRouter(prefix="/billing-approvals", tags=["billing approvals"])


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
