from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_request_meta
from app.core.audit import log_audit
from app.core.database import get_db
from app.core.permissions import user_has_permission
from app.models.leave import LeaveBillingCategory, LeaveStatus, LeaveType, TherapistLeave
from app.models.therapist_profile import TherapistProfile
from app.models.user import User
from app.services import leave_notification_service as leave_notify
from app.services import leave_policy_service as policy
from app.services import leave_service
from app.services.therapist_profile_service import get_or_create_profile

router = APIRouter(prefix="/leave", tags=["leave"])


class LeaveCreate(BaseModel):
    leave_type: Optional[LeaveType] = None
    service_line: str = Field(default="shadow_support", min_length=2, max_length=64)
    billing_category: Optional[LeaveBillingCategory] = None
    case_id: Optional[int] = None
    start_date: date
    end_date: date
    reason: Optional[str] = None


class LeaveReview(BaseModel):
    status: LeaveStatus
    review_note: Optional[str] = None


class LeaveBackfillUpdate(BaseModel):
    year: int = Field(..., ge=2000, le=2100)
    leave_paid_days_backfill: int = Field(0, ge=0)
    leave_carry_forward_days_backfill: int = Field(0, ge=0)
    leave_backfill_note: Optional[str] = None
    employment_start_date: Optional[date] = None


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
        "service_line": leave.service_line,
        "case_id": leave.case_id,
        "billing_category": leave.billing_category.value if leave.billing_category else None,
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


@router.get("/balance/{therapist_user_id}")
def leave_balance(
    therapist_user_id: int,
    year: int = Query(..., ge=2000, le=2100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if therapist_user_id != user.id and not user_has_permission(user, "leave.manage"):
        raise HTTPException(status_code=403, detail="Access denied")
    target = db.get(User, therapist_user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    return policy.get_leave_balance(db, target, year=year)


@router.get("/balance")
def my_leave_balance(
    year: int = Query(..., ge=2000, le=2100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return policy.get_leave_balance(db, user, year=year)


@router.get("/suggest")
def suggest_leave(
    start_date: date,
    end_date: date,
    service_line: str = Query(..., min_length=2),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if end_date < start_date:
        raise HTTPException(status_code=400, detail="end_date must be on or after start_date")
    if not policy.is_staff_leave_user(user):
        profile = db.scalars(select(TherapistProfile).where(TherapistProfile.user_id == user.id)).first()
        if not profile or not profile.employment_start_date:
            raise HTTPException(
                status_code=400,
                detail="Employment start date must be set on your profile before requesting leave.",
            )
    suggestion = policy.suggest_leave_split(
        db, user, start_date=start_date, end_date=end_date, service_line=service_line.strip().lower()
    )
    return {
        "paid_days": suggestion.paid_days,
        "carry_forward_days": suggestion.carry_forward_days,
        "unpaid_days": suggestion.unpaid_days,
        "total_days": suggestion.total_days,
        "message": suggestion.message,
    }


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
    summary = leave_service.build_summary(db, year=year, therapist_user_id=target_id)
    if target_id:
        target = db.get(User, target_id)
        if target:
            summary["leave_balance"] = policy.get_leave_balance(db, target, year=year)
    return summary


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
    for row in rows:
        tid = row.get("therapist_user_id")
        if tid:
            t = db.get(User, tid)
            if t:
                bal = policy.get_leave_balance(db, t, year=year)
                row["paid_remaining"] = bal["paid_remaining"]
                row["backfill_paid_used"] = bal["backfill_paid_used"]
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

    profile = None
    if not policy.is_staff_leave_user(user):
        profile = get_or_create_profile(db, user.id)
        if not profile.employment_start_date:
            raise HTTPException(
                status_code=400,
                detail="Employment start date must be set before requesting leave. Contact HR.",
            )

    service_line = payload.service_line.strip().lower()
    if not policy.is_staff_leave_user(user) and service_line != "shadow_support":
        raise HTTPException(
            status_code=400,
            detail="Leave requests are only available for shadow support. For homecare, cancel affected sessions instead.",
        )

    if payload.case_id is not None:
        from app.models.case import Case
        from app.core.permissions import get_active_assignment

        case = db.get(Case, payload.case_id)
        if not case:
            raise HTTPException(status_code=400, detail="Case not found")
        if (case.product_module or "").strip().lower() != "shadow_support":
            raise HTTPException(status_code=400, detail="Leave case must be a shadow support case")
        if not get_active_assignment(db, payload.case_id, user.id):
            raise HTTPException(status_code=400, detail="You are not assigned to this case")

    try:
        billing = policy.resolve_billing_category(
            db,
            user,
            start_date=payload.start_date,
            end_date=payload.end_date,
            service_line=service_line,
            requested_category=payload.billing_category,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    leave_type = payload.leave_type or policy.map_leave_type_from_billing(billing)

    leave = TherapistLeave(
        therapist_user_id=user.id,
        leave_type=leave_type,
        service_line=service_line,
        billing_category=billing,
        case_id=payload.case_id,
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
    out = _serialise(leave, db)
    sug = policy.suggest_leave_split(
        db, user, start_date=payload.start_date, end_date=payload.end_date, service_line=service_line
    )
    out["suggestion"] = {
        "paid_days": sug.paid_days,
        "carry_forward_days": sug.carry_forward_days,
        "unpaid_days": sug.unpaid_days,
        "total_days": sug.total_days,
        "message": sug.message,
    }
    return out


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
        if payload.status == LeaveStatus.REJECTED:
            note = (payload.review_note or "").strip()
            if not note:
                raise HTTPException(status_code=400, detail="Rejection comment is required")

    previous_status = leave.status
    leave.status = payload.status
    if payload.review_note is not None:
        leave.review_note = (payload.review_note or "").strip() or None
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
