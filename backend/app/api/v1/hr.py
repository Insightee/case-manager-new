from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_request_meta
from app.core.audit import log_audit
from app.core.database import get_db
from app.core.permissions import require_permission, user_has_permission
from app.models.memo import Memo
from app.models.user import EmploymentStatus, User

router = APIRouter(prefix="/hr", tags=["hr"])


class TherapistStatusUpdate(BaseModel):
    employment_status: Optional[str] = None
    region: Optional[str] = None
    location: Optional[str] = None
    module_assignments: Optional[list[str]] = None
    is_active: Optional[bool] = None


class MemoCreate(BaseModel):
    to_user_ids: list[int]
    subject: str
    body: str


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


@router.get("/therapists")
def list_therapists(
    search: Optional[str] = None,
    employment_status: Optional[str] = None,
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
        result.append(_serialise_user(t))
    return result


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
        target.module_assignments = payload.module_assignments
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
    )
    db.add(memo)
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="send_memo", entity_type="memo", entity_id=memo.id, **meta)
    db.commit()
    db.refresh(memo)
    return {"id": memo.id, "created_at": memo.created_at.isoformat()}
