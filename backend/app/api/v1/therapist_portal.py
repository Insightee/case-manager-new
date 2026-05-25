from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.permissions import user_has_permission
from app.models.user import User
from app.schemas.therapist_home import (
    TherapistHomeResponse,
    TherapistReportsPipelineResponse,
    TherapistSessionsWorkspaceResponse,
)
from app.services import therapist_home_service

router = APIRouter(prefix="/therapist", tags=["therapist-portal"])


def _require_therapist(user: User) -> None:
    if not user_has_permission(user, "case.read.assigned") and not user_has_permission(user, "case.read.all"):
        raise HTTPException(status_code=403, detail="Therapist access required")


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
