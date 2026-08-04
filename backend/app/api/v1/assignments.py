from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_request_meta
from app.core.audit import log_audit
from app.core.database import get_db
from app.core.billing_validation import apply_billing_payload, case_billing_dict
from app.core.module_write import ensure_case_write_access
from app.core.permissions import case_scope_check, require_mutation_permission
from app.models.assignment import CaseAssignment, CaseAssignmentStatus
from app.models.case import CaseStatus
from app.models.case_service import CaseService
from app.models.user import User
from app.schemas.case import AssignmentBookingUpdate, AssignmentCreate, AssignmentRead
from app.services import assignment_service, case_service

router = APIRouter(prefix="/cases/{case_id}/assignments", tags=["assignments"])


def _apply_post_assignment_billing(case, payload: AssignmentCreate, user_id: int) -> None:
    if payload.billing_update:
        apply_billing_payload(case, payload.billing_update, user_id)


def _create_case_assignment(db, case, case_id: int, payload: AssignmentCreate, user_id: int):
    try:
        if payload.case_service_id:
            service_line = db.get(CaseService, payload.case_service_id)
            if not service_line or service_line.case_id != case_id:
                raise HTTPException(status_code=404, detail="Service line not found")
            assignment = assignment_service.add_assignment_to_service(
                db,
                case_id=case_id,
                case_service_id=service_line.id,
                therapist_user_id=payload.therapist_user_id,
                assigned_by_user_id=user_id,
                start_date=payload.start_date or date.today(),
                reason_for_change=payload.reason_for_change,
                notes=payload.notes,
            )
        else:
            assignment = assignment_service.create_assignment(
                db,
                case_id=case_id,
                therapist_user_id=payload.therapist_user_id,
                assigned_by_user_id=user_id,
                start_date=payload.start_date or date.today(),
                reason_for_change=payload.reason_for_change,
                notes=payload.notes,
            )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _apply_post_assignment_billing(case, payload, user_id)
    return assignment


@router.get("", response_model=list[AssignmentRead])
def list_case_assignments(
    case_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    case = case_service.get_case(db, case_id)
    if not case or not case_scope_check(db, user, case):
        raise HTTPException(status_code=404, detail="Case not found")
    rows = assignment_service.list_assignments(db, case_id)
    billing = case_billing_dict(case) if case else None
    result = []
    for a in rows:
        therapist = db.get(User, a.therapist_user_id)
        data = assignment_service.assignment_to_read_dict(a, therapist.full_name if therapist else None)
        data["case_billing"] = billing
        result.append(AssignmentRead(**data))
    return result


@router.post("", response_model=AssignmentRead, status_code=status.HTTP_201_CREATED)
def assign_therapist(
    case_id: int,
    payload: AssignmentCreate,
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
    assignment = _create_case_assignment(db, case, case_id, payload, user.id)
    if case.status == CaseStatus.PENDING_ALLOTMENT:
        from app.services import client_status_service

        therapist = db.get(User, assignment.therapist_user_id)
        therapist_label = therapist.full_name if therapist else f"#{assignment.therapist_user_id}"
        reason = (payload.reason_for_change or "").strip()
        if len(reason) < 5:
            reason = f"Therapist allotted: {therapist_label}"
        try:
            client_status_service.change_client_status(
                db,
                case=case,
                user=user,
                new_status=CaseStatus.ACTIVE.value,
                effective_date=payload.start_date or date.today(),
                reason=reason,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="assign", entity_type="case_assignment", entity_id=assignment.id, new_value=payload.model_dump(), **meta)
    db.commit()
    therapist = db.get(User, assignment.therapist_user_id)
    data = assignment_service.assignment_to_read_dict(
        assignment, therapist.full_name if therapist else None
    )
    data["case_billing"] = case_billing_dict(case)
    return AssignmentRead(**data)


@router.get("/services/{service_id}/assignments", response_model=list[AssignmentRead])
def list_service_assignments(
    case_id: int,
    service_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    case = case_service.get_case(db, case_id)
    if not case or not case_scope_check(db, user, case):
        raise HTTPException(status_code=404, detail="Case not found")
    service_line = db.get(CaseService, service_id)
    if not service_line or service_line.case_id != case_id:
        raise HTTPException(status_code=404, detail="Service line not found")
    rows = [a for a in assignment_service.list_assignments(db, case_id) if a.case_service_id == service_id]
    billing = case_billing_dict(case)
    result = []
    for a in rows:
        therapist = db.get(User, a.therapist_user_id)
        data = assignment_service.assignment_to_read_dict(a, therapist.full_name if therapist else None)
        data["case_billing"] = billing
        result.append(AssignmentRead(**data))
    return result


@router.post("/services/{service_id}/assignments", response_model=AssignmentRead, status_code=status.HTTP_201_CREATED)
def assign_therapist_to_service(
    case_id: int,
    service_id: int,
    payload: AssignmentCreate,
    request: Request,
    user: User = Depends(require_mutation_permission("case.assign")),
    db: Session = Depends(get_db),
):
    case = case_service.get_case(db, case_id)
    if not case or not case_scope_check(db, user, case):
        raise HTTPException(status_code=404, detail="Case not found")
    ensure_case_write_access(user, case, db)
    service_line = db.get(CaseService, service_id)
    if not service_line or service_line.case_id != case_id:
        raise HTTPException(status_code=404, detail="Service line not found")
    assignment = assignment_service.add_assignment_to_service(
        db,
        case_id=case_id,
        case_service_id=service_line.id,
        therapist_user_id=payload.therapist_user_id,
        assigned_by_user_id=user.id,
        start_date=payload.start_date or date.today(),
        reason_for_change=payload.reason_for_change,
        notes=payload.notes,
    )
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="assign_service", entity_type="case_assignment", entity_id=assignment.id, new_value=payload.model_dump(), **meta)
    db.commit()
    therapist = db.get(User, assignment.therapist_user_id)
    data = assignment_service.assignment_to_read_dict(assignment, therapist.full_name if therapist else None)
    data["case_billing"] = case_billing_dict(case)
    return AssignmentRead(**data)


@router.post("/services/{service_id}/assignments/replace", response_model=AssignmentRead, status_code=status.HTTP_201_CREATED)
def replace_service_assignment(
    case_id: int,
    service_id: int,
    payload: AssignmentCreate,
    request: Request,
    user: User = Depends(require_mutation_permission("case.assign")),
    db: Session = Depends(get_db),
):
    case = case_service.get_case(db, case_id)
    if not case or not case_scope_check(db, user, case):
        raise HTTPException(status_code=404, detail="Case not found")
    ensure_case_write_access(user, case, db)
    service_line = db.get(CaseService, service_id)
    if not service_line or service_line.case_id != case_id:
        raise HTTPException(status_code=404, detail="Service line not found")
    try:
        assignment = assignment_service.replace_assignment_in_service(
            db,
            case_id=case_id,
            case_service_id=service_line.id,
            therapist_user_id=payload.therapist_user_id,
            assigned_by_user_id=user.id,
            start_date=payload.start_date or date.today(),
            reason_for_change=payload.reason_for_change,
            notes=payload.notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _apply_post_assignment_billing(case, payload, user.id)
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="replace_service_assignment", entity_type="case_assignment", entity_id=assignment.id, new_value=payload.model_dump(), **meta)
    db.commit()
    therapist = db.get(User, assignment.therapist_user_id)
    data = assignment_service.assignment_to_read_dict(assignment, therapist.full_name if therapist else None)
    data["case_billing"] = case_billing_dict(case)
    return AssignmentRead(**data)


@router.post("/services/{service_id}/assignments/{assignment_id}/end", response_model=AssignmentRead)
def end_service_assignment(
    case_id: int,
    service_id: int,
    assignment_id: int,
    request: Request,
    user: User = Depends(require_mutation_permission("case.assign")),
    db: Session = Depends(get_db),
):
    case = case_service.get_case(db, case_id)
    if not case or not case_scope_check(db, user, case):
        raise HTTPException(status_code=404, detail="Case not found")
    ensure_case_write_access(user, case, db)
    service_line = db.get(CaseService, service_id)
    if not service_line or service_line.case_id != case_id:
        raise HTTPException(status_code=404, detail="Service line not found")
    assignment = db.get(CaseAssignment, assignment_id)
    if not assignment or assignment.case_id != case_id or assignment.case_service_id != service_id:
        raise HTTPException(status_code=404, detail="Assignment not found")
    if assignment.status == CaseAssignmentStatus.ACTIVE:
        assignment.status = CaseAssignmentStatus.ENDED
        assignment.end_date = date.today()
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="end_service_assignment", entity_type="case_assignment", entity_id=assignment.id, **meta)
    db.commit()
    therapist = db.get(User, assignment.therapist_user_id)
    data = assignment_service.assignment_to_read_dict(assignment, therapist.full_name if therapist else None)
    data["case_billing"] = case_billing_dict(case)
    return AssignmentRead(**data)


@router.patch("/{assignment_id}/booking", response_model=AssignmentRead)
def update_assignment_booking(
    case_id: int,
    assignment_id: int,
    payload: AssignmentBookingUpdate,
    user: User = Depends(require_mutation_permission("case.assign")),
    db: Session = Depends(get_db),
):
    case = case_service.get_case(db, case_id)
    if not case or not case_scope_check(db, user, case):
        raise HTTPException(status_code=404, detail="Case not found")
    ensure_case_write_access(user, case, db)
    assignment = db.get(CaseAssignment, assignment_id)
    if not assignment or assignment.case_id != case_id:
        raise HTTPException(status_code=404, detail="Assignment not found")
    try:
        assignment = assignment_service.update_assignment_booking(
            db, assignment_id, payload.model_dump(exclude_unset=True)
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    db.commit()
    therapist = db.get(User, assignment.therapist_user_id)
    data = assignment_service.assignment_to_read_dict(
        assignment, therapist.full_name if therapist else None
    )
    data["case_billing"] = case_billing_dict(case)
    return AssignmentRead(**data)
