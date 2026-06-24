from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_request_meta
from app.core.audit import log_audit
from app.core.database import get_db
from app.core.permissions import require_permission
from app.models.user import User
from app.schemas.session_absence import (
    SessionAbsenceCreate,
    SessionAbsenceListResponse,
    SessionAbsenceRead,
    SessionAbsenceReview,
    SessionAbsenceStatusResponse,
)
from app.services import session_absence_service as absence_svc

router = APIRouter(prefix="/sessions", tags=["session-absence"])


@router.post("/{session_id}/absence", response_model=SessionAbsenceRead, status_code=201)
def create_session_absence(
    session_id: int,
    payload: SessionAbsenceCreate,
    request: Request,
    user: User = Depends(require_permission("session.update")),
    db: Session = Depends(get_db),
):
    try:
        detail = absence_svc.create_request(
            db,
            user,
            session_id,
            absence_type=payload.absence_type,
            reason=payload.reason,
            notes=payload.notes,
            leave_billing_category=payload.leave_billing_category,
        )
    except HTTPException:
        raise
    meta = get_request_meta(request)
    log_audit(
        db,
        actor_user_id=user.id,
        action="create_session_absence",
        entity_type="session_absence",
        entity_id=detail["id"],
        case_id=detail["case_id"],
        **meta,
    )
    db.commit()
    return detail


@router.get("/{session_id}/absence", response_model=SessionAbsenceStatusResponse)
def get_session_absence(
    session_id: int,
    user: User = Depends(require_permission("session.update")),
    db: Session = Depends(get_db),
):
    return absence_svc.get_absence_for_session(db, user, session_id)


@router.get("/absence/pending", response_model=SessionAbsenceListResponse)
def list_pending_absence_admin(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    items = absence_svc.list_pending_for_admin(db, user)
    return {"items": items}


@router.post("/absence/{request_id}/approve", response_model=SessionAbsenceRead)
def approve_session_absence(
    request_id: int,
    payload: SessionAbsenceReview,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    detail = absence_svc.approve_request(db, user, request_id, review_note=payload.review_note)
    meta = get_request_meta(request)
    log_audit(
        db,
        actor_user_id=user.id,
        action="approve_session_absence",
        entity_type="session_absence",
        entity_id=request_id,
        case_id=detail["case_id"],
        **meta,
    )
    db.commit()
    return detail


@router.post("/absence/{request_id}/reject", response_model=SessionAbsenceRead)
def reject_session_absence(
    request_id: int,
    payload: SessionAbsenceReview,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    detail = absence_svc.reject_request(db, user, request_id, review_note=payload.review_note)
    meta = get_request_meta(request)
    log_audit(
        db,
        actor_user_id=user.id,
        action="reject_session_absence",
        entity_type="session_absence",
        entity_id=request_id,
        case_id=detail["case_id"],
        **meta,
    )
    db.commit()
    return detail
