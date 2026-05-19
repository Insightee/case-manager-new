from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_request_meta
from app.core.audit import log_audit
from app.core.database import get_db
from app.core.permissions import user_has_permission
from app.models.leave import LeaveStatus, LeaveType, TherapistLeave
from app.models.user import User
from app.services import leave_notification_service as leave_notify

router = APIRouter(prefix="/leave", tags=["leave"])


class LeaveCreate(BaseModel):
    leave_type: LeaveType
    start_date: date
    end_date: date
    reason: Optional[str] = None


class LeaveReview(BaseModel):
    status: LeaveStatus
    review_note: Optional[str] = None


def _serialise(leave: TherapistLeave) -> dict:
    return {
        "id": leave.id,
        "therapist_user_id": leave.therapist_user_id,
        "leave_type": leave.leave_type.value,
        "start_date": leave.start_date.isoformat(),
        "end_date": leave.end_date.isoformat(),
        "reason": leave.reason,
        "status": leave.status.value,
        "reviewed_by_user_id": leave.reviewed_by_user_id,
        "review_note": leave.review_note,
        "created_at": leave.created_at.isoformat(),
        "updated_at": leave.updated_at.isoformat(),
    }


@router.get("")
def list_leave(
    therapist_id: Optional[int] = None,
    leave_status: Optional[LeaveStatus] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stmt = select(TherapistLeave).order_by(TherapistLeave.created_at.desc())
    if user_has_permission(user, "leave.manage"):
        if therapist_id:
            stmt = stmt.where(TherapistLeave.therapist_user_id == therapist_id)
    else:
        stmt = stmt.where(TherapistLeave.therapist_user_id == user.id)
    if leave_status:
        stmt = stmt.where(TherapistLeave.status == leave_status)
    leaves = db.scalars(stmt).all()
    return [_serialise(l) for l in leaves]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_leave(
    payload: LeaveCreate,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if payload.end_date < payload.start_date:
        raise HTTPException(status_code=400, detail="end_date must be on or after start_date")
    leave = TherapistLeave(
        therapist_user_id=user.id,
        leave_type=payload.leave_type,
        start_date=payload.start_date,
        end_date=payload.end_date,
        reason=payload.reason,
    )
    db.add(leave)
    db.flush()
    leave_notify.notify_leave_submitted(db, leave, user)
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="create", entity_type="leave", entity_id=leave.id, **meta)
    db.commit()
    db.refresh(leave)
    return _serialise(leave)


@router.patch("/{leave_id}")
def review_leave(
    leave_id: int,
    payload: LeaveReview,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    leave = db.get(TherapistLeave, leave_id)
    if not leave:
        raise HTTPException(status_code=404, detail="Leave request not found")

    if payload.status == LeaveStatus.CANCELLED:
        if leave.therapist_user_id != user.id:
            raise HTTPException(status_code=403, detail="Can only cancel your own leave")
        if leave.status != LeaveStatus.PENDING:
            raise HTTPException(status_code=400, detail="Only pending leave can be cancelled")
    else:
        if not user_has_permission(user, "leave.manage"):
            raise HTTPException(status_code=403, detail="leave.manage permission required")
        if leave.status != LeaveStatus.PENDING:
            raise HTTPException(status_code=400, detail="Leave has already been reviewed")

    previous_status = leave.status
    leave.status = payload.status
    if payload.review_note is not None:
        leave.review_note = payload.review_note
    if payload.status in (LeaveStatus.APPROVED, LeaveStatus.REJECTED):
        leave.reviewed_by_user_id = user.id

    therapist = db.get(User, leave.therapist_user_id)
    if therapist and previous_status == LeaveStatus.PENDING:
        if payload.status == LeaveStatus.APPROVED:
            leave_notify.notify_leave_approved(db, leave, therapist)
        elif payload.status == LeaveStatus.REJECTED:
            leave_notify.notify_leave_rejected(db, leave, therapist)

    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="review_leave", entity_type="leave", entity_id=leave_id, **meta)
    db.commit()
    db.refresh(leave)
    return _serialise(leave)


@router.delete("/{leave_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_leave(
    leave_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    leave = db.get(TherapistLeave, leave_id)
    if not leave:
        raise HTTPException(status_code=404, detail="Leave request not found")
    if leave.therapist_user_id != user.id and not user_has_permission(user, "leave.manage"):
        raise HTTPException(status_code=403, detail="Access denied")
    if leave.status != LeaveStatus.PENDING:
        raise HTTPException(status_code=400, detail="Only pending leave can be deleted")
    db.delete(leave)
    db.commit()
