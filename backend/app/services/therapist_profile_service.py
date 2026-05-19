from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.permissions import RoleName
from app.core.therapist_services import SERVICE_CATEGORIES, validate_service_ids
from app.models.therapist_profile import TherapistProfile, TherapistProfileStatus
from app.models.user import User


def _normalize_certs(certs: list[str] | None) -> list[str]:
    if not certs:
        return []
    return [c.strip() for c in certs if c and c.strip()]


def profile_to_dict(profile: TherapistProfile, user: User | None = None) -> dict:
    u = user or profile.user
    return {
        "id": profile.id,
        "user_id": profile.user_id,
        "display_name": profile.display_name,
        "short_bio": profile.short_bio,
        "academic_qualifications": profile.academic_qualifications,
        "professional_certificates": profile.professional_certificates or [],
        "services_offered": profile.services_offered or [],
        "status": profile.status.value,
        "admin_note": profile.admin_note,
        "submitted_at": profile.submitted_at,
        "reviewed_at": profile.reviewed_at,
        "email": u.email if u else None,
        "full_name": u.full_name if u else None,
    }


def get_or_create_profile(db: Session, user_id: int) -> TherapistProfile:
    profile = db.scalars(select(TherapistProfile).where(TherapistProfile.user_id == user_id)).first()
    if profile:
        return profile
    profile = TherapistProfile(user_id=user_id, status=TherapistProfileStatus.DRAFT)
    db.add(profile)
    db.flush()
    return profile


def apply_profile_fields(profile: TherapistProfile, data: dict) -> None:
    if "display_name" in data:
        profile.display_name = data["display_name"]
    if "short_bio" in data:
        profile.short_bio = data["short_bio"]
    if "academic_qualifications" in data:
        profile.academic_qualifications = data["academic_qualifications"]
    if "professional_certificates" in data:
        profile.professional_certificates = _normalize_certs(data["professional_certificates"])
    if "services_offered" in data:
        try:
            profile.services_offered = validate_service_ids(data["services_offered"] or [])
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e


def therapist_save_profile(db: Session, user: User, data: dict) -> TherapistProfile:
    if RoleName.THERAPIST.value not in user.role_names:
        raise HTTPException(status_code=403, detail="Therapist access only")
    profile = get_or_create_profile(db, user.id)
    if profile.status == TherapistProfileStatus.PAUSED:
        raise HTTPException(status_code=400, detail="Profile is paused. Contact admin to resume.")
    apply_profile_fields(profile, data)
    if profile.status == TherapistProfileStatus.APPROVED:
        profile.status = TherapistProfileStatus.DRAFT
    db.flush()
    return profile


def therapist_submit_profile(db: Session, user: User) -> TherapistProfile:
    profile = get_or_create_profile(db, user.id)
    if profile.status == TherapistProfileStatus.PAUSED:
        raise HTTPException(status_code=400, detail="Profile is paused")
    if not (profile.services_offered or []):
        raise HTTPException(status_code=400, detail="Select at least one service you offer")
    if not (profile.display_name or user.full_name):
        raise HTTPException(status_code=400, detail="Display name is required")
    profile.status = TherapistProfileStatus.PENDING
    profile.submitted_at = datetime.now(timezone.utc)
    profile.admin_note = None
    db.flush()
    return profile


def list_profiles(db: Session, status: TherapistProfileStatus | None = None) -> list[TherapistProfile]:
    stmt = select(TherapistProfile).order_by(TherapistProfile.updated_at.desc())
    if status:
        stmt = stmt.where(TherapistProfile.status == status)
    return list(db.scalars(stmt).all())


def service_categories() -> list[dict[str, str]]:
    return list(SERVICE_CATEGORIES)
