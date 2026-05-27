from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_request_meta
from app.core.audit import log_audit
from app.core.database import get_db
from app.core.permissions import require_permission, user_has_permission
from app.models.user import User
from app.schemas.session import TherapistClientIntakeCreate, TherapistClientIntakeResponse
from app.schemas.session_log_portal import (
    SessionLogCreate,
    SessionLogRead,
    TherapistMyCasesResponse,
)
from app.schemas.therapist_home import (
    TherapistHomeResponse,
    TherapistReportsPipelineResponse,
    TherapistSessionsWorkspaceResponse,
)
from app.services import session_log_service, therapist_home_service, therapist_intake_service

router = APIRouter(prefix="/therapist", tags=["therapist-portal"])


def _require_therapist(user: User) -> None:
    if not user_has_permission(user, "case.read.assigned") and not user_has_permission(user, "case.read.all"):
        raise HTTPException(status_code=403, detail="Therapist access required")


@router.get("/my-cases", response_model=TherapistMyCasesResponse)
def therapist_my_cases(
    user: User = Depends(require_permission("case.read.assigned")),
    db: Session = Depends(get_db),
):
    _require_therapist(user)
    data = session_log_service.list_therapist_my_cases(db, user)
    return TherapistMyCasesResponse(**data)


@router.post("/session-logs", response_model=SessionLogRead, status_code=status.HTTP_201_CREATED)
def therapist_create_session_log(
    payload: SessionLogCreate,
    request: Request,
    user: User = Depends(require_permission("daily_log.create")),
    db: Session = Depends(get_db),
):
    _require_therapist(user)
    try:
        log = session_log_service.create_therapist_session_log(db, user, payload.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    meta = get_request_meta(request)
    log_audit(
        db,
        actor_user_id=user.id,
        action="create",
        entity_type="daily_log",
        entity_id=log.id,
        new_value=payload.model_dump(),
        **meta,
    )
    db.commit()
    return SessionLogRead(**session_log_service.session_log_read(db, log))


@router.get("/home", response_model=TherapistHomeResponse)
def therapist_home(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_therapist(user)
    return therapist_home_service.build_therapist_home(db, user)


@router.get("/sessions/workspace", response_model=TherapistSessionsWorkspaceResponse)
def therapist_sessions_workspace(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_therapist(user)
    return therapist_home_service.build_sessions_workspace(db, user)


@router.get("/reports/pipeline", response_model=TherapistReportsPipelineResponse)
def therapist_reports_pipeline(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_therapist(user)
    return therapist_home_service.build_reports_pipeline(db, user)


@router.post("/client-intake", response_model=TherapistClientIntakeResponse, status_code=201)
def therapist_client_intake(
    payload: TherapistClientIntakeCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.core.permissions import user_has_permission

    if not user_has_permission(user, "session.create"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    _require_therapist(user)
    try:
        result = therapist_intake_service.create_client_intake(
            db,
            therapist_user_id=user.id,
            client_name=payload.client_name,
            client_email=str(payload.client_email),
            child_name=payload.child_name,
            client_phone=payload.client_phone,
            product_module=payload.product_module,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    case = result["case"]
    db.commit()
    from app.services import case_service

    case = case_service.get_case(db, case.id)
    child_name = case.child.full_name if case and case.child else payload.child_name
    return TherapistClientIntakeResponse(
        case_id=case.id,
        case_code=case.case_code,
        child_name=child_name,
        parent_email=result["parent_email"],
        invite_sent=result["invite_sent"],
        invite_url=result.get("invite_url"),
    )
