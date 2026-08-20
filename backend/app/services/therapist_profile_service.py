from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.permissions import RoleName
from app.core.therapist_services import get_service_categories, validate_service_ids
from app.models.therapist_profile import TherapistProfile, TherapistProfileStatus
from app.models.user import User


def _normalize_certs(certs: list[str] | None) -> list[str]:
    if not certs:
        return []
    return [c.strip() for c in certs if c and c.strip()]


# Therapist-editable listing fields reviewed before publish.
SNAPSHOT_FIELDS = (
    "display_name",
    "short_bio",
    "academic_qualifications",
    "professional_certificates",
    "services_offered",
)


def build_profile_snapshot(profile: TherapistProfile) -> dict:
    """Capture the therapist-editable fields that were just approved."""
    return {
        "display_name": profile.display_name,
        "short_bio": profile.short_bio,
        "academic_qualifications": profile.academic_qualifications,
        "professional_certificates": list(profile.professional_certificates or []),
        "services_offered": list(profile.services_offered or []),
    }


def build_submission_snapshot(data: dict, db: Session | None = None) -> dict:
    services = data.get("services_offered") or []
    if db is not None and services:
        try:
            services = validate_service_ids(services, db)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
    return {
        "display_name": (data.get("display_name") or "").strip() or None,
        "short_bio": (data.get("short_bio") or "").strip() or None,
        "academic_qualifications": (data.get("academic_qualifications") or "").strip() or None,
        "professional_certificates": _normalize_certs(data.get("professional_certificates")),
        "services_offered": list(services),
    }


def capture_approved_snapshot(profile: TherapistProfile) -> None:
    """Store the current editable fields as the new approved baseline."""
    profile.approved_snapshot = build_profile_snapshot(profile)


def has_pending_submission(profile: TherapistProfile) -> bool:
    return bool(profile.pending_submission)


def apply_snapshot_to_profile(profile: TherapistProfile, snapshot: dict) -> None:
    for key in SNAPSHOT_FIELDS:
        if key not in snapshot:
            continue
        value = snapshot[key]
        if key in ("professional_certificates", "services_offered"):
            profile.__setattr__(key, list(value or []))
        else:
            profile.__setattr__(key, value)


def apply_pending_submission(profile: TherapistProfile) -> None:
    pending = profile.pending_submission
    if not pending:
        return
    apply_snapshot_to_profile(profile, pending)
    profile.pending_submission = None


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
        "approved_snapshot": profile.approved_snapshot,
        "pending_submission": profile.pending_submission,
        "has_pending_changes": has_pending_submission(profile),
    }


def get_or_create_profile(db: Session, user_id: int) -> TherapistProfile:
    profile = db.scalars(select(TherapistProfile).where(TherapistProfile.user_id == user_id)).first()
    if profile:
        return profile
    profile = TherapistProfile(user_id=user_id, status=TherapistProfileStatus.DRAFT)
    db.add(profile)
    db.flush()
    return profile


def _validate_staff_user_id(db: Session, user_id: int | None, *, field_label: str) -> None:
    if user_id is None:
        return
    user = db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=400, detail=f"Selected {field_label} is not available. Refresh and try again.")


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
        new_cm = data["supervisor_user_id"]
        if db is not None:
            _validate_staff_user_id(db, new_cm, field_label="case manager")
        profile.supervisor_user_id = new_cm
        if new_cm and db is not None:
            from app.services.assignment_service import sync_case_managers_for_therapist

            sync_case_managers_for_therapist(db, profile.user_id, new_cm)
    if "mentor_user_id" in data:
        if db is not None:
            from app.services.mentor_scope_service import validate_mentor_is_case_manager

            validate_mentor_is_case_manager(db, data["mentor_user_id"])
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


def _validate_submission_payload(data: dict, user: User, db: Session) -> dict:
    submission = build_submission_snapshot(data, db)
    if not submission["services_offered"]:
        raise HTTPException(status_code=400, detail="Select at least one service you offer")
    if not (submission["display_name"] or user.full_name):
        raise HTTPException(status_code=400, detail="Display name is required")
    return submission


def therapist_submit_profile(db: Session, user: User, data: dict) -> TherapistProfile:
    if RoleName.THERAPIST.value not in user.role_names:
        raise HTTPException(status_code=403, detail="Therapist access only")
    profile = get_or_create_profile(db, user.id)
    if profile.status == TherapistProfileStatus.PAUSED:
        raise HTTPException(status_code=400, detail="Profile is paused")

    submission = _validate_submission_payload(data, user, db)
    if not submission["display_name"]:
        submission["display_name"] = user.full_name

    operational = {}
    if "employment_start_date" in data:
        operational["employment_start_date"] = data["employment_start_date"] or None

    if profile.approved_snapshot:
        profile.pending_submission = submission
        apply_snapshot_to_profile(profile, profile.approved_snapshot)
        if operational:
            apply_profile_fields(profile, operational, db)
        profile.status = TherapistProfileStatus.APPROVED
    else:
        apply_profile_fields(profile, {**submission, **operational}, db)
        profile.status = TherapistProfileStatus.PENDING
        profile.pending_submission = None

    profile.submitted_at = datetime.now(timezone.utc)
    profile.admin_note = None
    db.flush()
    return profile


def admin_approve_profile(profile: TherapistProfile, admin_note: str | None = None) -> None:
    if profile.pending_submission:
        apply_pending_submission(profile)
    profile.status = TherapistProfileStatus.APPROVED
    if admin_note:
        profile.admin_note = admin_note
    capture_approved_snapshot(profile)


def list_profiles(db: Session, status: TherapistProfileStatus | None = None) -> list[TherapistProfile]:
    stmt = select(TherapistProfile).order_by(TherapistProfile.updated_at.desc())
    if status == TherapistProfileStatus.PENDING:
        # Review queue: first submissions + approved listings with unreviewed edits.
        stmt = stmt.where(
            or_(
                TherapistProfile.status == TherapistProfileStatus.PENDING,
                TherapistProfile.pending_submission.isnot(None),
            )
        )
    elif status == TherapistProfileStatus.APPROVED:
        # Match summary counts: pending edits belong in PENDING, not APPROVED.
        stmt = stmt.where(
            TherapistProfile.status == TherapistProfileStatus.APPROVED,
            TherapistProfile.pending_submission.is_(None),
        )
    elif status:
        stmt = stmt.where(TherapistProfile.status == status)
    return list(db.scalars(stmt).all())


def profile_summary_counts(profiles: list[TherapistProfile]) -> dict[str, int]:
    counts = {"PENDING": 0, "DRAFT": 0, "APPROVED": 0, "PAUSED": 0}
    for profile in profiles:
        if has_pending_submission(profile):
            counts["PENDING"] += 1
            continue
        key = profile.status.value if hasattr(profile.status, "value") else str(profile.status)
        if key in counts:
            counts[key] += 1
    return counts


def service_categories(db: Session) -> list[dict[str, str]]:
    return get_service_categories(db)
