from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_request_meta
from app.core.audit import log_audit
from app.core.database import get_db
from app.core.module_access import user_has_feature
from app.core.permissions import RoleName, case_scope_check, require_permission, user_has_permission
from app.models.daily_log import LogApprovalStatus
from app.models.user import User
from app.models.visibility import VisibilityStatus
from app.schemas.daily_log import DailyLogCreate, DailyLogFinanceRead, DailyLogRead, DailyLogUpdate
from app.services import case_service, log_service

router = APIRouter(prefix="/daily-logs", tags=["daily-logs"])


def _log_case_scope(db: Session, user: User, log) -> None:
    if not log.session:
        raise HTTPException(status_code=404, detail="Log not found")
    case = case_service.get_case(db, log.session.case_id)
    if not case or not case_scope_check(db, user, case):
        raise HTTPException(status_code=403, detail="Case access denied")


@router.get("")
def list_daily_logs(
    therapist_user_id: Optional[int] = None,
    case_id: Optional[int] = None,
    month: Optional[str] = None,
    product_module: Optional[str] = None,
    approval_status: Optional[LogApprovalStatus] = None,
    late_addition: Optional[bool] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not user_has_permission(user, "session.read") and not user_has_permission(user, "daily_log.review"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    if user_has_permission(user, "session.read") and not user_has_feature(user, "session_logs") and not user_has_permission(user, "daily_log.create"):
        raise HTTPException(status_code=403, detail="Session logs module access required")
    logs = log_service.list_logs(db, therapist_user_id=therapist_user_id, case_id=case_id, month=month, product_module=product_module)
    if approval_status is not None:
        logs = [l for l in logs if l.approval_status == approval_status]
    if late_addition is not None:
        logs = [l for l in logs if bool(l.late_addition) == late_addition]
    scoped = []
    for log in logs:
        if not log.session:
            continue
        case = case_service.get_case(db, log.session.case_id)
        if case and case_scope_check(db, user, case):
            scoped.append(log)
    logs = scoped
    is_finance = RoleName.FINANCE.value in user.role_names and RoleName.SUPER_ADMIN.value not in user.role_names
    if is_finance:
        return [DailyLogFinanceRead(**log_service.log_to_read(l, include_clinical=False)) for l in logs]
    return [DailyLogRead(**log_service.log_to_read(l)) for l in logs]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_daily_log(
    payload: DailyLogCreate,
    request: Request,
    user: User = Depends(require_permission("daily_log.create")),
    db: Session = Depends(get_db),
):
    try:
        log = log_service.create_daily_log(db, **payload.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="create", entity_type="daily_log", entity_id=log.id, new_value=payload.model_dump(), **meta)
    db.commit()
    return DailyLogRead(**log_service.log_to_read(log))


@router.patch("/{log_id}", response_model=DailyLogRead)
def update_daily_log(
    log_id: int,
    payload: DailyLogUpdate,
    request: Request,
    user: User = Depends(require_permission("daily_log.create")),
    db: Session = Depends(get_db),
):
    log = log_service.get_log(db, log_id)
    if not log:
        raise HTTPException(status_code=404, detail="Log not found")
    try:
        log = log_service.update_daily_log(db, log, user.id, **payload.model_dump(exclude_unset=True))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="update", entity_type="daily_log", entity_id=log.id, **meta)
    db.commit()
    return DailyLogRead(**log_service.log_to_read(log))


@router.post("/{log_id}/approve")
def approve_log(
    log_id: int,
    request: Request,
    user: User = Depends(require_permission("daily_log.review")),
    db: Session = Depends(get_db),
):
    log = log_service.get_log(db, log_id)
    if not log:
        raise HTTPException(status_code=404, detail="Log not found")
    _log_case_scope(db, user, log)
    log.approval_status = LogApprovalStatus.APPROVED
    if not log.submitted_at:
        log.submitted_at = datetime.now(timezone.utc)
    if log.parent_notes:
        log.visibility_status = VisibilityStatus.APPROVED_FOR_PARENT
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="approve", entity_type="daily_log", entity_id=log.id, **meta)
    db.commit()
    return {"status": "approved"}


@router.post("/{log_id}/reject")
def reject_log(
    log_id: int,
    request: Request,
    user: User = Depends(require_permission("daily_log.review")),
    db: Session = Depends(get_db),
):
    log = log_service.get_log(db, log_id)
    if not log:
        raise HTTPException(status_code=404, detail="Log not found")
    _log_case_scope(db, user, log)
    log.approval_status = LogApprovalStatus.REJECTED
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="reject", entity_type="daily_log", entity_id=log.id, **meta)
    db.commit()
    return {"status": "rejected"}
