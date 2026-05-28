from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_request_meta
from app.core.audit import log_audit
from app.core.database import get_db
from app.core.module_write import ensure_case_write_access
from app.core.permissions import case_scope_check, require_mutation_permission
from app.models.case_service import CaseService
from app.models.assignment import CaseAssignment, CaseAssignmentStatus
from app.models.user import User
from app.schemas.case import (
    AssignmentCreate,
    AssignmentRead,
    CaseServiceCreate,
    CaseServiceRead,
    CaseServiceUpdate,
)
from app.services import assignment_service, case_service, case_service_service

router = APIRouter(prefix="/cases/{case_id}/services", tags=["case-services"])


@router.get("", response_model=list[CaseServiceRead])
def list_case_services(
    case_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    case = case_service.get_case(db, case_id)
    if not case or not case_scope_check(db, user, case):
        raise HTTPException(status_code=404, detail="Case not found")
    return case_service_service.list_case_services(db, case_id)


@router.post("", response_model=CaseServiceRead, status_code=status.HTTP_201_CREATED)
def create_case_service(
    case_id: int,
    payload: CaseServiceCreate,
    user: User = Depends(require_mutation_permission("case.assign")),
    db: Session = Depends(get_db),
):
    case = case_service.get_case(db, case_id)
    if not case or not case_scope_check(db, user, case):
        raise HTTPException(status_code=404, detail="Case not found")
    ensure_case_write_access(user, case, db)
    try:
        row = case_service_service.create_case_service(
            db,
            case_id=case_id,
            service_key=payload.service_key,
            product_module=payload.product_module or case.product_module,
            start_date=payload.start_date,
            notes=payload.notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    db.commit()
    db.refresh(row)
    return row


@router.patch("/{service_id}", response_model=CaseServiceRead)
def update_case_service(
    case_id: int,
    service_id: int,
    payload: CaseServiceUpdate,
    user: User = Depends(require_mutation_permission("case.assign")),
    db: Session = Depends(get_db),
):
    case = case_service.get_case(db, case_id)
    if not case or not case_scope_check(db, user, case):
        raise HTTPException(status_code=404, detail="Case not found")
    ensure_case_write_access(user, case, db)
    row = case_service_service.get_case_service(db, service_id)
    if not row or row.case_id != case_id:
        raise HTTPException(status_code=404, detail="Service line not found")
    try:
        row = case_service_service.update_case_service(
            db,
            case_service_id=service_id,
            status=payload.status,
            end_date=payload.end_date,
            notes=payload.notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    db.commit()
    db.refresh(row)
    return row


@router.get("/{service_id}/assignments", response_model=list[AssignmentRead])
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
    result = []
    for a in rows:
        therapist = db.get(User, a.therapist_user_id)
        result.append(AssignmentRead(**assignment_service.assignment_to_read_dict(a, therapist.full_name if therapist else None)))
    return result


@router.post("/{service_id}/assignments", response_model=AssignmentRead, status_code=status.HTTP_201_CREATED)
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
    try:
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
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="assign_service", entity_type="case_assignment", entity_id=assignment.id, new_value=payload.model_dump(), **meta)
    db.commit()
    therapist = db.get(User, assignment.therapist_user_id)
    return AssignmentRead(**assignment_service.assignment_to_read_dict(assignment, therapist.full_name if therapist else None))


@router.post("/{service_id}/assignments/replace", response_model=AssignmentRead, status_code=status.HTTP_201_CREATED)
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
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="replace_service_assignment", entity_type="case_assignment", entity_id=assignment.id, new_value=payload.model_dump(), **meta)
    db.commit()
    therapist = db.get(User, assignment.therapist_user_id)
    return AssignmentRead(**assignment_service.assignment_to_read_dict(assignment, therapist.full_name if therapist else None))


@router.post("/{service_id}/assignments/{assignment_id}/end", response_model=AssignmentRead)
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
    return AssignmentRead(**assignment_service.assignment_to_read_dict(assignment, therapist.full_name if therapist else None))
