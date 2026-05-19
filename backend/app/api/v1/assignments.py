from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_request_meta
from app.core.audit import log_audit
from app.core.database import get_db
from app.core.billing_validation import case_billing_dict
from app.core.permissions import case_scope_check, require_permission
from app.models.case import CaseStatus
from app.models.user import User
from app.schemas.case import AssignmentCreate, AssignmentRead
from app.services import assignment_service, case_service

router = APIRouter(prefix="/cases/{case_id}/assignments", tags=["assignments"])


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
        result.append(
        AssignmentRead(
            id=a.id,
            case_id=a.case_id,
            therapist_user_id=a.therapist_user_id,
            therapist_name=therapist.full_name if therapist else None,
            assigned_by_user_id=a.assigned_by_user_id,
            start_date=a.start_date,
            end_date=a.end_date,
            status=a.status.value,
            reason_for_change=a.reason_for_change,
            notes=a.notes,
            case_billing=billing,
        )
        )
    return result


@router.post("", response_model=AssignmentRead, status_code=status.HTTP_201_CREATED)
def assign_therapist(
    case_id: int,
    payload: AssignmentCreate,
    request: Request,
    user: User = Depends(require_permission("case.assign")),
    db: Session = Depends(get_db),
):
    case = case_service.get_case(db, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    if not case_scope_check(db, user, case):
        raise HTTPException(status_code=403, detail="Case access denied")
    assignment = assignment_service.create_assignment(
        db,
        case_id=case_id,
        therapist_user_id=payload.therapist_user_id,
        assigned_by_user_id=user.id,
        start_date=payload.start_date or date.today(),
        reason_for_change=payload.reason_for_change,
        notes=payload.notes,
    )
    if case.status == CaseStatus.PENDING_ALLOTMENT:
        case.status = CaseStatus.ACTIVE
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="assign", entity_type="case_assignment", entity_id=assignment.id, new_value=payload.model_dump(), **meta)
    db.commit()
    return AssignmentRead(
        id=assignment.id,
        case_id=assignment.case_id,
        therapist_user_id=assignment.therapist_user_id,
        assigned_by_user_id=assignment.assigned_by_user_id,
        start_date=assignment.start_date,
        end_date=assignment.end_date,
        status=assignment.status.value,
        reason_for_change=assignment.reason_for_change,
        notes=assignment.notes,
        case_billing=case_billing_dict(case),
    )
