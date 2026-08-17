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
from app.core.module_write import ensure_case_write_access
from app.core.permissions import case_scope_check, require_mutation_permission
from app.models.assignment import CaseAssignment, CaseAssignmentStatus
from app.models.case_therapist_transition import CaseTherapistTransition
from app.models.user import User
from app.services import case_service, therapist_transition_service

router = APIRouter(prefix="/cases/{case_id}/transitions", tags=["therapist-transitions"])


class TherapistTransitionCreate(BaseModel):
    incoming_therapist_user_id: int
    transition_dates: list[str] = Field(min_length=3, max_length=3)
    billing_update: dict
    notes: Optional[str] = None


class TherapistTransitionRead(BaseModel):
    id: int
    case_id: int
    case_service_id: int
    outgoing_therapist_user_id: int
    outgoing_therapist_name: Optional[str] = None
    incoming_therapist_user_id: int
    incoming_therapist_name: Optional[str] = None
    outgoing_assignment_id: int
    incoming_assignment_id: int
    transition_dates: list[str]
    status: str
    pending_billing_update: dict
    day_type: Optional[str] = None
    full_day_pay_inr: float
    half_day_pay_inr: float
    locked_dates: list[str] = Field(default_factory=list)
    can_cancel: bool = False
    notes: Optional[str] = None
    created_by_user_id: int
    created_by_name: Optional[str] = None
    completed_at: Optional[str] = None
    cancelled_at: Optional[str] = None
    cancellation_reason: Optional[str] = None
    created_at: Optional[str] = None


class TherapistTransitionDatesUpdate(BaseModel):
    transition_dates: list[str] = Field(min_length=3, max_length=3)


class TherapistTransitionCancel(BaseModel):
    reason: Optional[str] = Field(default=None, max_length=1000)


@router.get("", response_model=list[TherapistTransitionRead])
def list_case_transitions(
    case_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    case = case_service.get_case(db, case_id)
    if not case or not case_scope_check(db, user, case):
        raise HTTPException(status_code=404, detail="Case not found")
    therapist_transition_service.complete_due_transitions(db)
    db.commit()
    rows = therapist_transition_service.list_transitions_for_case(db, case_id)
    return [TherapistTransitionRead(**therapist_transition_service.transition_to_read_dict(db, row)) for row in rows]


@router.get("/active", response_model=Optional[TherapistTransitionRead])
def get_active_case_transition(
    case_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    case = case_service.get_case(db, case_id)
    if not case or not case_scope_check(db, user, case):
        raise HTTPException(status_code=404, detail="Case not found")
    therapist_transition_service.complete_due_transitions(db)
    db.commit()
    row = therapist_transition_service.active_transition_for_case(db, case_id)
    if not row:
        return None
    return TherapistTransitionRead(**therapist_transition_service.transition_to_read_dict(db, row))


@router.get("/availability")
def get_transition_availability(
    case_id: int,
    incoming_therapist_user_id: int,
    start_date: date,
    end_date: date,
    outgoing_therapist_user_id: Optional[int] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    case = case_service.get_case(db, case_id)
    if not case or not case_scope_check(db, user, case):
        raise HTTPException(status_code=404, detail="Case not found")
    if end_date < start_date or (end_date - start_date).days > 62:
        raise HTTPException(status_code=400, detail="Choose an availability range of up to 63 days.")
    outgoing_stmt = (
        select(CaseAssignment.therapist_user_id)
        .where(
            CaseAssignment.case_id == case_id,
            CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
        )
        .order_by(CaseAssignment.id.desc())
        .limit(1)
    )
    if outgoing_therapist_user_id is not None:
        outgoing_stmt = outgoing_stmt.where(
            CaseAssignment.therapist_user_id == outgoing_therapist_user_id
        )
    outgoing_id = db.scalars(outgoing_stmt).first()
    if not outgoing_id:
        raise HTTPException(status_code=400, detail="Assign a primary therapist first.")
    unavailable = therapist_transition_service.unavailable_transition_dates(
        db,
        case_id=case_id,
        therapist_user_ids={outgoing_id, incoming_therapist_user_id},
        start_date=start_date,
        end_date=end_date,
    )
    return {
        "unavailable_dates": sorted(unavailable),
        "therapist_ids_by_date": unavailable,
    }


@router.post("", response_model=TherapistTransitionRead, status_code=status.HTTP_201_CREATED)
def create_case_transition(
    case_id: int,
    payload: TherapistTransitionCreate,
    request: Request,
    user: User = Depends(require_mutation_permission("case.assign")),
    db: Session = Depends(get_db),
):
    case = case_service.get_case(db, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    if not case_scope_check(db, user, case):
        raise HTTPException(status_code=403, detail="Case access denied")
    ensure_case_write_access(user, case, db)
    try:
        transition = therapist_transition_service.create_transition(
            db,
            case_id=case_id,
            incoming_therapist_user_id=payload.incoming_therapist_user_id,
            transition_dates=payload.transition_dates,
            billing_update=payload.billing_update,
            created_by_user_id=user.id,
            notes=payload.notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    meta = get_request_meta(request)
    log_audit(
        db,
        actor_user_id=user.id,
        action="create",
        entity_type="case_therapist_transition",
        entity_id=transition.id,
        case_id=case_id,
        new_value=payload.model_dump(),
        **meta,
    )
    db.commit()
    return TherapistTransitionRead(**therapist_transition_service.transition_to_read_dict(db, transition))


@router.patch("/{transition_id}/dates", response_model=TherapistTransitionRead)
def update_case_transition_dates(
    case_id: int,
    transition_id: int,
    payload: TherapistTransitionDatesUpdate,
    request: Request,
    user: User = Depends(require_mutation_permission("case.assign")),
    db: Session = Depends(get_db),
):
    case = case_service.get_case(db, case_id)
    if not case or not case_scope_check(db, user, case):
        raise HTTPException(status_code=404, detail="Case not found")
    ensure_case_write_access(user, case, db, allow_during_transition=True)
    transition = db.get(CaseTherapistTransition, transition_id)
    if not transition or transition.case_id != case_id:
        raise HTTPException(status_code=404, detail="Transition not found")
    try:
        transition = therapist_transition_service.update_transition_dates(
            db,
            transition,
            transition_dates=payload.transition_dates,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    meta = get_request_meta(request)
    log_audit(
        db,
        actor_user_id=user.id,
        action="update_dates",
        entity_type="case_therapist_transition",
        entity_id=transition.id,
        case_id=case_id,
        new_value=payload.model_dump(),
        **meta,
    )
    db.commit()
    return TherapistTransitionRead(**therapist_transition_service.transition_to_read_dict(db, transition))


@router.post("/{transition_id}/cancel", response_model=TherapistTransitionRead)
def cancel_case_transition(
    case_id: int,
    transition_id: int,
    payload: TherapistTransitionCancel,
    request: Request,
    user: User = Depends(require_mutation_permission("case.assign")),
    db: Session = Depends(get_db),
):
    case = case_service.get_case(db, case_id)
    if not case or not case_scope_check(db, user, case):
        raise HTTPException(status_code=404, detail="Case not found")
    ensure_case_write_access(user, case, db, allow_during_transition=True)
    transition = db.get(CaseTherapistTransition, transition_id)
    if not transition or transition.case_id != case_id:
        raise HTTPException(status_code=404, detail="Transition not found")
    try:
        transition = therapist_transition_service.cancel_transition(
            db,
            transition,
            actor_user_id=user.id,
            reason=payload.reason,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    meta = get_request_meta(request)
    log_audit(
        db,
        actor_user_id=user.id,
        action="cancel",
        entity_type="case_therapist_transition",
        entity_id=transition.id,
        case_id=case_id,
        new_value=payload.model_dump(),
        **meta,
    )
    db.commit()
    return TherapistTransitionRead(**therapist_transition_service.transition_to_read_dict(db, transition))
