from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_request_meta
from app.core.audit import log_audit
from app.core.database import get_db
from app.core.permissions import RoleName, require_permission
from app.models.assignment import CaseAssignment
from app.models.user import User
from app.schemas.case import AssignmentRead
from app.services import assignment_service
from app.services import assignment_acceptance_service as accept_svc

router = APIRouter(prefix="/assignments", tags=["assignments"])


@router.post("/{assignment_id}/accept", response_model=AssignmentRead)
def therapist_accept_assignment(
    assignment_id: int,
    request: Request,
    user: User = Depends(require_permission("session.update")),
    db: Session = Depends(get_db),
):
    if RoleName.THERAPIST.value not in user.role_names:
        raise HTTPException(status_code=403, detail="Therapist access required")
    try:
        assignment = accept_svc.accept_assignment_as_therapist(db, assignment_id, user.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    meta = get_request_meta(request)
    log_audit(
        db,
        actor_user_id=user.id,
        action="accept_assignment",
        entity_type="case_assignment",
        entity_id=assignment.id,
        **meta,
    )
    db.commit()
    therapist = db.get(User, assignment.therapist_user_id)
    data = assignment_service.assignment_to_read_dict(
        assignment, therapist.full_name if therapist else None
    )
    return AssignmentRead(**data)
