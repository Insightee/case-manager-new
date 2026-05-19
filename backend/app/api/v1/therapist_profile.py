from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_request_meta
from app.core.audit import log_audit
from app.core.database import get_db
from app.core.permissions import RoleName
from app.models.user import User
from app.schemas.therapist_profile import (
    ServiceCategoryRead,
    TherapistProfileRead,
    TherapistProfileUpdate,
)
from app.services import therapist_profile_service as svc

router = APIRouter(prefix="/therapist", tags=["therapist-profile"])


def _require_therapist(user: User) -> None:
    if RoleName.THERAPIST.value not in user.role_names:
        raise HTTPException(status_code=403, detail="Therapist access only")


@router.get("/service-categories", response_model=list[ServiceCategoryRead])
def list_service_categories():
    return [ServiceCategoryRead(**c) for c in svc.service_categories()]


@router.get("/profile", response_model=TherapistProfileRead)
def get_my_profile(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_therapist(user)
    profile = svc.get_or_create_profile(db, user.id)
    db.commit()
    return TherapistProfileRead(**svc.profile_to_dict(profile, user))


@router.put("/profile", response_model=TherapistProfileRead)
def save_my_profile(
    payload: TherapistProfileUpdate,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_therapist(user)
    profile = svc.therapist_save_profile(db, user, payload.model_dump(exclude_unset=True))
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="save_profile", entity_type="therapist_profile", entity_id=profile.id, **meta)
    db.commit()
    db.refresh(profile)
    return TherapistProfileRead(**svc.profile_to_dict(profile, user))


@router.post("/profile/submit", response_model=TherapistProfileRead)
def submit_my_profile(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_therapist(user)
    profile = svc.therapist_submit_profile(db, user)
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="submit_profile", entity_type="therapist_profile", entity_id=profile.id, **meta)
    db.commit()
    db.refresh(profile)
    return TherapistProfileRead(**svc.profile_to_dict(profile, user))
