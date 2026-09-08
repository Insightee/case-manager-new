"""Mentor therapist roster — list, assign, and unassign mentored therapists."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.permissions import RoleName, user_has_permission
from app.models.assignment import CaseAssignment, CaseAssignmentStatus
from app.models.therapist_profile import TherapistProfile
from app.models.user import User
from app.services.mentor_scope_service import validate_mentor_is_case_manager


def _require_roster_access(user: User, *, for_self: bool) -> None:
    if user_has_permission(user, "user.manage"):
        return
    if for_self and RoleName.CASE_MANAGER.value in (user.role_names or []):
        return
    raise HTTPException(status_code=403, detail="Not allowed to manage mentor roster")


def _profile_row(db: Session, profile: TherapistProfile) -> dict:
    therapist = profile.user
    primary_cm_name = None
    if profile.supervisor_user_id:
        cm = db.get(User, profile.supervisor_user_id)
        primary_cm_name = cm.full_name if cm else None
    active_cases = int(
        db.scalar(
            select(func.count())
            .select_from(CaseAssignment)
            .where(
                CaseAssignment.therapist_user_id == profile.user_id,
                CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
            )
        )
        or 0
    )
    return {
        "therapist_user_id": profile.user_id,
        "profile_id": profile.id,
        "full_name": therapist.full_name if therapist else None,
        "email": therapist.email if therapist else None,
        "display_name": profile.display_name,
        "services_offered": profile.services_offered or [],
        "primary_case_manager_user_id": profile.supervisor_user_id,
        "primary_case_manager_name": primary_cm_name,
        "mentor_user_id": profile.mentor_user_id,
        "active_case_count": active_cases,
        "last_session_log_at": profile.last_session_log_at.isoformat()
        if getattr(profile, "last_session_log_at", None)
        else None,
    }


def list_mentored_therapists(db: Session, user: User) -> dict:
    _require_roster_access(user, for_self=True)
    if not user_has_permission(user, "therapist.read") and not user_has_permission(user, "user.manage"):
        raise HTTPException(status_code=403, detail="Therapist read permission required")

    mentor_id = user.id
    if user_has_permission(user, "user.manage"):
        pass

    profiles = db.scalars(
        select(TherapistProfile)
        .where(TherapistProfile.mentor_user_id == mentor_id)
        .order_by(TherapistProfile.id)
    ).all()
    return {
        "mentor_user_id": mentor_id,
        "total": len(profiles),
        "therapists": [_profile_row(db, p) for p in profiles],
    }


def list_available_therapists_for_mentor(db: Session, user: User) -> dict:
    """Therapists with no mentor — mentors may claim; admins see all unmentored."""
    _require_roster_access(user, for_self=True)
    if not user_has_permission(user, "therapist.read") and not user_has_permission(user, "user.manage"):
        raise HTTPException(status_code=403, detail="Therapist read permission required")

    stmt = (
        select(TherapistProfile)
        .where(TherapistProfile.mentor_user_id.is_(None))
        .order_by(TherapistProfile.id)
        .limit(500)
    )
    profiles = db.scalars(stmt).all()
    return {
        "total": len(profiles),
        "therapists": [_profile_row(db, p) for p in profiles],
    }


def assign_mentor(
    db: Session,
    actor: User,
    therapist_user_id: int,
    *,
    mentor_user_id: int | None = None,
) -> dict:
    """Assign mentor to therapist. Self-service uses actor as mentor; admin may specify."""
    target_mentor_id = mentor_user_id if mentor_user_id is not None else actor.id
    if mentor_user_id is None:
        _require_roster_access(actor, for_self=True)
    else:
        if not user_has_permission(actor, "user.manage"):
            raise HTTPException(status_code=403, detail="Admin permission required to assign another mentor")

    validate_mentor_is_case_manager(db, target_mentor_id)

    therapist = db.get(User, therapist_user_id)
    if not therapist or RoleName.THERAPIST.value not in (therapist.role_names or []):
        raise HTTPException(status_code=404, detail="Therapist not found")

    profile = db.scalars(
        select(TherapistProfile).where(TherapistProfile.user_id == therapist_user_id)
    ).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Therapist profile not found")

    if mentor_user_id is None and profile.mentor_user_id and profile.mentor_user_id != actor.id:
        raise HTTPException(
            status_code=400,
            detail="This therapist already has a mentor. Ask an admin to reassign.",
        )

    old_mentor_id = profile.mentor_user_id
    profile.mentor_user_id = target_mentor_id
    db.flush()
    return {
        "therapist_user_id": therapist_user_id,
        "mentor_user_id": target_mentor_id,
        "previous_mentor_user_id": old_mentor_id,
        "therapist": _profile_row(db, profile),
    }


def unassign_mentor(
    db: Session,
    actor: User,
    therapist_user_id: int,
) -> dict:
    profile = db.scalars(
        select(TherapistProfile).where(TherapistProfile.user_id == therapist_user_id)
    ).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Therapist profile not found")
    if not profile.mentor_user_id:
        raise HTTPException(status_code=400, detail="Therapist has no mentor assigned")

    if user_has_permission(actor, "user.manage"):
        pass
    elif profile.mentor_user_id == actor.id and RoleName.CASE_MANAGER.value in (actor.role_names or []):
        pass
    else:
        raise HTTPException(status_code=403, detail="Not allowed to remove this mentor assignment")

    old_mentor_id = profile.mentor_user_id
    profile.mentor_user_id = None
    db.flush()
    return {
        "therapist_user_id": therapist_user_id,
        "previous_mentor_user_id": old_mentor_id,
        "therapist": _profile_row(db, profile),
    }
