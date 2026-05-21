from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
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
from app.services import leave_service

router = APIRouter(prefix="/leave", tags=["leave"])


class LeaveCreate(BaseModel):
    leave_type: LeaveType
    start_date: date
    end_date: date
    reason: Optional[str] = None


class LeaveReview(BaseModel):
    status: LeaveStatus
    review_note: Optional[str] = None


def _user_name(db: Session, user_id: Optional[int]) -> Optional[str]:
    if not user_id:
        return None
    u = db.get(User, user_id)
    return u.full_name if u else None


def _serialise(leave: TherapistLeave, db: Session) -> dict:
    return {
        "id": leave.id,
        "therapist_user_id": leave.therapist_user_id,
        "therapist_name": _user_name(db, leave.therapist_user_id),
        "leave_type": leave.leave_type.value,
        "start_date": leave.start_date.isoformat(),
        "end_date": leave.end_date.isoformat(),
        "day_count": leave_service.leave_day_count(leave.start_date, leave.end_date),
        "reason": leave.reason,
        "status": leave.status.value,
        "reviewed_by_user_id": leave.reviewed_by_user_id,
        "reviewer_name": _user_name(db, leave.reviewed_by_user_id),
        "review_note": leave.review_note,
        "reviewed_at": leave.updated_at.isoformat() if leave.reviewed_by_user_id else None,
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
    return [_serialise(l, db) for l in leaves]


@router.get("/summary")
def leave_summary(
    year: int = Query(..., ge=2000, le=2100),
    therapist_id: Optional[int] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if user_has_permission(user, "leave.manage"):
        target_id = therapist_id
    else:
        target_id = user.id
        if therapist_id is not None and therapist_id != user.id:
            raise HTTPException(status_code=403, detail="Access denied")
    return leave_service.build_summary(db, year=year, therapist_user_id=target_id)


@router.get("/report")
def leave_report(
    year: int = Query(..., ge=2000, le=2100),
    granularity: str = Query("monthly", pattern="^(monthly|yearly)$"),
    format: Optional[str] = Query(None, alias="format"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not user_has_permission(user, "leave.manage"):
        raise HTTPException(status_code=403, detail="leave.manage permission required")
    rows = leave_service.build_report(db, year=year, granularity=granularity)
    if format == "csv":
        csv_text = leave_service.report_to_csv(rows)
        return Response(
            content=csv_text,
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="leave-report-{year}.csv"'},
        )
    return {"year": year, "granularity": granularity, "rows": rows}


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
    return _serialise(leave, db)


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
    return _serialise(leave, db)


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
    leave_notify.unblock_slots_for_leave(db, leave.id)
    db.delete(leave)
    db.commit()
