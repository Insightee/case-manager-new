from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_request_meta
from app.core.audit import log_audit
from app.core.database import get_db
from app.core.permissions import RoleName, require_permission, user_has_permission
from app.models.memo import Memo
from app.models.user import EmploymentStatus, User

router = APIRouter(prefix="/hr", tags=["hr"])


class TherapistStatusUpdate(BaseModel):
    employment_status: Optional[str] = None
    region: Optional[str] = None
    location: Optional[str] = None
    module_assignments: Optional[list[str]] = None
    is_active: Optional[bool] = None


class TherapistLeaveBackfillUpdate(BaseModel):
    year: int = Field(..., ge=2000, le=2100)
    leave_paid_days_backfill: int = Field(0, ge=0)
    leave_carry_forward_days_backfill: int = Field(0, ge=0)
    leave_backfill_note: Optional[str] = None
    employment_start_date: Optional[date] = None


class MemoCreate(BaseModel):
    to_user_ids: list[int]
    subject: str
    body: str
    send_as_email: bool = False


def _serialise_user(u: User) -> dict:
    return {
        "id": u.id,
        "email": u.email,
        "full_name": u.full_name,
        "is_active": u.is_active,
        "employment_status": (u.employment_status.value if u.employment_status else "ACTIVE"),
        "location": u.location,
        "region": u.region,
        "roles": u.role_names,
        "module_assignments": u.module_assignments or [],
        "created_at": u.created_at.isoformat(),
    }


@router.get("/ops-snapshot")
def hr_ops_snapshot(
    user: User = Depends(require_permission("therapist.read")),
    db: Session = Depends(get_db),
):
    from app.services.hr_ops_snapshot_service import build_hr_ops_snapshot

    return build_hr_ops_snapshot(db, user)


@router.get("/recipients")
def list_memo_recipients(
    search: Optional[str] = None,
    user: User = Depends(require_permission("memo.send")),
    db: Session = Depends(get_db),
):
    from app.models.role import Role
    from sqlalchemy.orm import selectinload

    stmt = (
        select(User)
        .join(User.roles)
        .where(Role.name.in_(("THERAPIST", "CASE_MANAGER", "MODULE_ADMIN", "HR", "FINANCE", "ADMIN")))
        .options(selectinload(User.roles))
        .order_by(User.full_name)
    )
    rows = db.scalars(stmt).unique().all()
    out = []
    q = (search or "").strip().lower()
    for u in rows:
        if not u.is_active:
            continue
        hay = f"{u.full_name} {u.email} {' '.join(u.role_names)}".lower()
        if q and q not in hay:
            continue
        out.append(
            {
                "id": u.id,
                "full_name": u.full_name,
                "email": u.email,
                "roles": u.role_names,
                "kind": "therapist" if "THERAPIST" in u.role_names else "staff",
            }
        )
    return out


@router.get("/therapists")
def list_therapists(
    search: Optional[str] = None,
    employment_status: Optional[str] = None,
    include_leave_balance: bool = False,
    year: Optional[int] = None,
    user: User = Depends(require_permission("therapist.read")),
    db: Session = Depends(get_db),
):
    from app.models.role import Role
    from sqlalchemy.orm import selectinload

    stmt = (
        select(User)
        .join(User.roles)
        .where(Role.name == "THERAPIST")
        .options(selectinload(User.roles))
        .order_by(User.full_name)
    )
    therapists = db.scalars(stmt).unique().all()
    result = []
    for t in therapists:
        if search and search.lower() not in t.full_name.lower() and search.lower() not in t.email.lower():
            continue
        if employment_status and (t.employment_status.value if t.employment_status else "ACTIVE") != employment_status:
            continue
        row = _serialise_user(t)
        if include_leave_balance and user_has_permission(user, "leave.manage"):
            from app.services import leave_policy_service as policy

            bal_year = year or date.today().year
            row["leave_balance"] = policy.get_leave_balance(db, t, year=bal_year)
        result.append(row)
    return result


@router.patch("/therapists/{user_id}/leave-backfill")
def update_therapist_leave_backfill(
    user_id: int,
    payload: TherapistLeaveBackfillUpdate,
    request: Request,
    user: User = Depends(require_permission("leave.manage")),
    db: Session = Depends(get_db),
):
    from app.models.role import Role
    from app.services import leave_policy_service as policy
    from app.services.therapist_profile_service import apply_leave_backfill, get_or_create_profile

    target = db.get(User, user_id)
    if not target or RoleName.THERAPIST.value not in target.role_names:
        raise HTTPException(status_code=404, detail="Therapist not found")
    profile = get_or_create_profile(db, user_id)
    apply_leave_backfill(
        profile,
        year=payload.year,
        paid_backfill=payload.leave_paid_days_backfill,
        carry_backfill=payload.leave_carry_forward_days_backfill,
        note=payload.leave_backfill_note,
        employment_start_date=payload.employment_start_date,
        actor_user_id=user.id,
    )
    meta = get_request_meta(request)
    log_audit(
        db,
        actor_user_id=user.id,
        action="update_leave_backfill",
        entity_type="therapist_profile",
        entity_id=profile.id,
        **meta,
    )
    db.commit()
    return {
        "user_id": user_id,
        "leave_balance": policy.get_leave_balance(db, target, year=payload.year),
    }


@router.patch("/therapists/{user_id}")
def update_therapist(
    user_id: int,
    payload: TherapistStatusUpdate,
    request: Request,
    user: User = Depends(require_permission("therapist.read")),
    db: Session = Depends(get_db),
):
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if "THERAPIST" not in target.role_names:
        raise HTTPException(status_code=400, detail="Target user is not a therapist")

    if payload.employment_status is not None:
        try:
            target.employment_status = EmploymentStatus(payload.employment_status)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid employment_status value")
        target.is_active = (target.employment_status == EmploymentStatus.ACTIVE)
    if payload.region is not None:
        target.region = payload.region
    if payload.location is not None:
        target.location = payload.location
    if payload.module_assignments is not None:
        from app.core.module_access import validate_module_assignments

        target.module_assignments = validate_module_assignments(
            target.role_names, payload.module_assignments
        )
    if payload.is_active is not None:
        target.is_active = payload.is_active

    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="update_therapist", entity_type="user", entity_id=user_id, **meta)
    db.commit()
    db.refresh(target)
    return _serialise_user(target)


@router.get("/memos")
def list_memos(
    user: User = Depends(require_permission("memo.send")),
    db: Session = Depends(get_db),
):
    memos = db.scalars(
        select(Memo).where(Memo.from_user_id == user.id).order_by(Memo.created_at.desc())
    ).all()
    return [
        {
            "id": m.id,
            "to_user_ids": m.to_user_ids,
            "subject": m.subject,
            "body": m.body,
            "created_at": m.created_at.isoformat(),
        }
        for m in memos
    ]


@router.post("/memos", status_code=status.HTTP_201_CREATED)
def send_memo(
    payload: MemoCreate,
    request: Request,
    user: User = Depends(require_permission("memo.send")),
    db: Session = Depends(get_db),
):
    if not payload.to_user_ids:
        raise HTTPException(status_code=400, detail="At least one recipient required")
    memo = Memo(
        from_user_id=user.id,
        to_user_ids=payload.to_user_ids,
        subject=payload.subject,
        body=payload.body,
        send_as_email=payload.send_as_email,
    )
    db.add(memo)
    db.flush()
    email_sent = False
    if payload.send_as_email:
        from datetime import datetime, timezone

        from app.services import email_service

        recipients = []
        for uid in payload.to_user_ids:
            target = db.get(User, uid)
            if target and target.email:
                recipients.append(target.email)
        if recipients:
            email_sent = email_service.send_email(
                to=recipients,
                subject=payload.subject,
                body_text=payload.body,
            )
            if email_sent:
                memo.email_sent_at = datetime.now(timezone.utc)
    meta = get_request_meta(request)
    log_audit(
        db,
        actor_user_id=user.id,
        action="send_memo",
        entity_type="memo",
        entity_id=memo.id,
        new_value={"send_as_email": payload.send_as_email, "email_sent": email_sent},
        **meta,
    )
    db.commit()
    db.refresh(memo)
    return {
        "id": memo.id,
        "created_at": memo.created_at.isoformat(),
        "email_sent": bool(memo.email_sent_at),
    }
