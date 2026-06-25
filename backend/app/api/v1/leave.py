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
from app.core.permissions import RoleName, user_has_permission
from app.models.leave import LeaveBillingCategory, LeaveStatus, LeaveType, TherapistLeave
from app.models.user import User
from app.schemas.session_absence import SessionAbsenceListResponse
from app.services import leave_migration_service as leave_migration
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
    case_ids: Optional[list[int]] = None
    start_date: date
    end_date: date
    reason: Optional[str] = None
    consulted_with_parents: bool = False


class ManualLeaveCreate(LeaveCreate):
    therapist_user_id: int = Field(..., ge=1)


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
    retro = leave_migration.is_retroactive_leave(leave.start_date, leave.end_date)
    return {
        "id": leave.id,
        "therapist_user_id": leave.therapist_user_id,
        "therapist_name": _user_name(db, leave.therapist_user_id),
        "leave_type": leave.leave_type.value,
        "service_line": leave.service_line,
        "case_id": leave.case_id,
        "case_ids": leave.case_ids or ([] if leave.case_id is None else [leave.case_id]),
        "billing_category": leave.billing_category.value if leave.billing_category else None,
        "paid_days": leave.paid_days,
        "unpaid_days": leave.unpaid_days,
        "includes_shadow_cases": leave.includes_shadow_cases,
        "consulted_with_parents": leave.consulted_with_parents,
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
        "is_retroactive": retro,
        "is_migration_reentry": leave_migration.is_migration_reentry(leave.start_date, leave.end_date),
    }


def _split_response(suggestion: policy.LeaveSplitSuggestion) -> dict:
    return {
        "paid_days": suggestion.paid_days,
        "unpaid_days": suggestion.unpaid_days,
        "total_days": suggestion.total_days,
        "has_shadow_cases": suggestion.has_shadow_cases,
        "message": suggestion.message,
        "carry_forward_days": 0,
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


@router.get("/child-absence", response_model=SessionAbsenceListResponse)
def list_child_absence_requests(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.services import session_absence_service as absence_svc

    if not user_has_permission(user, "leave.manage") and not user_has_permission(user, "case.read.all"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    return {"items": absence_svc.list_child_absence_for_admin(db, user)}


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


@router.get("/migration-info")
def leave_migration_info(user: User = Depends(get_current_user)):
    return leave_migration.migration_info_payload()


@router.get("/suggest")
def suggest_leave(
    start_date: date,
    end_date: date,
    service_line: str = Query(default="shadow_support", min_length=2),
    therapist_id: Optional[int] = None,
    case_ids: Optional[str] = Query(None, description="Comma-separated case ids"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if end_date < start_date:
        raise HTTPException(status_code=400, detail="end_date must be on or after start_date")
    target = user
    if therapist_id is not None:
        if not user_has_permission(user, "leave.manage"):
            raise HTTPException(status_code=403, detail="Access denied")
        target = db.get(User, therapist_id)
        if not target or RoleName.THERAPIST.value not in target.role_names:
            raise HTTPException(status_code=404, detail="Therapist not found")
    parsed_case_ids: list[int] | None = None
    if case_ids:
        try:
            parsed_case_ids = [int(x.strip()) for x in case_ids.split(",") if x.strip()]
        except ValueError as e:
            raise HTTPException(status_code=400, detail="Invalid case_ids") from e
    suggestion = policy.suggest_leave_split(
        db,
        target,
        start_date=start_date,
        end_date=end_date,
        service_line=service_line.strip().lower(),
        case_ids=parsed_case_ids,
    )
    return _split_response(suggestion)


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
                row["paid_remaining"] = bal["leave_credit_pending"]
                row["backfill_paid_used"] = bal["paid_leaves_taken"]
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
    get_or_create_profile(db, user.id)

    try:
        leave = leave_service.create_therapist_leave_request(
            db,
            therapist=user,
            start_date=payload.start_date,
            end_date=payload.end_date,
            service_line=payload.service_line,
            billing_category=payload.billing_category,
            case_id=payload.case_id,
            case_ids=payload.case_ids,
            reason=payload.reason,
            leave_type=payload.leave_type,
            consulted_with_parents=payload.consulted_with_parents,
            auto_approve=False,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="create", entity_type="leave", entity_id=leave.id, **meta)
    db.commit()
    db.refresh(leave)
    out = _serialise(leave, db)
    sug = policy.compute_leave_split(
        db,
        user,
        start_date=payload.start_date,
        end_date=payload.end_date,
        case_ids=leave.case_ids or ([] if leave.case_id is None else [leave.case_id]),
    )
    out["suggestion"] = _split_response(sug)
    return out


@router.post("/manual", status_code=status.HTTP_201_CREATED)
def create_manual_leave(
    payload: ManualLeaveCreate,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not user_has_permission(user, "leave.manage"):
        raise HTTPException(status_code=403, detail="leave.manage permission required")

    therapist = db.get(User, payload.therapist_user_id)
    if not therapist or RoleName.THERAPIST.value not in therapist.role_names:
        raise HTTPException(status_code=404, detail="Therapist not found")

    try:
        leave = leave_service.create_therapist_leave_request(
            db,
            therapist=therapist,
            start_date=payload.start_date,
            end_date=payload.end_date,
            service_line=payload.service_line,
            billing_category=payload.billing_category,
            case_id=payload.case_id,
            case_ids=payload.case_ids,
            reason=payload.reason,
            leave_type=payload.leave_type,
            consulted_with_parents=payload.consulted_with_parents,
            auto_approve=True,
            reviewer_user_id=user.id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    meta = get_request_meta(request)
    log_audit(
        db,
        actor_user_id=user.id,
        action="create_manual_leave",
        entity_type="leave",
        entity_id=leave.id,
        **meta,
    )
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
