from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Optional

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
    supervisor_name = None
    mentor_name = None
    if getattr(profile, "supervisor_user_id", None):
        sup = getattr(profile, "supervisor", None)
        if sup:
            supervisor_name = sup.full_name
    if getattr(profile, "mentor_user_id", None):
        men = getattr(profile, "mentor", None)
        if men:
            mentor_name = men.full_name
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
        "supervisor_user_id": getattr(profile, "supervisor_user_id", None),
        "mentor_user_id": getattr(profile, "mentor_user_id", None),
        "supervisor_name": supervisor_name,
        "mentor_name": mentor_name,
        "employment_start_date": profile.employment_start_date,
        "leave_balance_year": profile.leave_balance_year,
        "leave_paid_days_backfill": int(profile.leave_paid_days_backfill or 0),
        "leave_carry_forward_days_backfill": int(profile.leave_carry_forward_days_backfill or 0),
        "leave_backfill_note": profile.leave_backfill_note,
    }


def get_or_create_profile(db: Session, user_id: int) -> TherapistProfile:
    profile = db.scalars(select(TherapistProfile).where(TherapistProfile.user_id == user_id)).first()
    if profile:
        return profile
    profile = TherapistProfile(user_id=user_id, status=TherapistProfileStatus.DRAFT)
    db.add(profile)
    db.flush()
    return profile


def apply_profile_fields(profile: TherapistProfile, data: dict, db: Session | None = None) -> None:
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
            profile.services_offered = validate_service_ids(data["services_offered"] or [], db)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
    if "supervisor_user_id" in data:
        profile.supervisor_user_id = data["supervisor_user_id"]
    if "mentor_user_id" in data:
        profile.mentor_user_id = data["mentor_user_id"]
    if "employment_start_date" in data:
        profile.employment_start_date = data["employment_start_date"]
    if "leave_balance_year" in data:
        profile.leave_balance_year = data["leave_balance_year"]
    if "leave_paid_days_backfill" in data:
        profile.leave_paid_days_backfill = int(data["leave_paid_days_backfill"] or 0)
    if "leave_carry_forward_days_backfill" in data:
        profile.leave_carry_forward_days_backfill = int(data["leave_carry_forward_days_backfill"] or 0)
    if "leave_backfill_note" in data:
        profile.leave_backfill_note = (data["leave_backfill_note"] or "").strip() or None


def apply_leave_backfill(
    profile: TherapistProfile,
    *,
    year: int,
    paid_backfill: int,
    carry_backfill: int,
    note: Optional[str],
    employment_start_date: Optional[date],
    actor_user_id: int,
) -> None:
    if paid_backfill < 0 or carry_backfill < 0:
        raise HTTPException(status_code=400, detail="Backfill days cannot be negative")
    if (paid_backfill > 0 or carry_backfill > 0) and not (note or "").strip():
        raise HTTPException(status_code=400, detail="Note is required when backfill days are set")
    profile.leave_balance_year = year
    profile.leave_paid_days_backfill = paid_backfill
    profile.leave_carry_forward_days_backfill = carry_backfill
    profile.leave_backfill_note = (note or "").strip() or None
    if employment_start_date is not None:
        profile.employment_start_date = employment_start_date
    profile.leave_backfill_updated_at = datetime.now(timezone.utc)
    profile.leave_backfill_updated_by_user_id = actor_user_id


def therapist_save_profile(db: Session, user: User, data: dict) -> TherapistProfile:
    if RoleName.THERAPIST.value not in user.role_names:
        raise HTTPException(status_code=403, detail="Therapist access only")
    profile = get_or_create_profile(db, user.id)
    if profile.status == TherapistProfileStatus.PAUSED:
        raise HTTPException(status_code=400, detail="Profile is paused. Contact admin to resume.")
    apply_profile_fields(profile, data, db)
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
