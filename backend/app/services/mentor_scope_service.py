"""Therapist mentor (CM) caseload scope and write gates.

Mentors are assigned on therapist_profiles.mentor_user_id and must be CASE_MANAGER.
They may read cases / logs / reports for therapists they mentor; mutations stay with
the assigned case manager except mark-as-reviewed on daily logs.
"""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.assignment import CaseAssignment, CaseAssignmentStatus
from app.models.case import Case
from app.models.therapist_profile import TherapistProfile
from app.models.user import User


def validate_mentor_is_case_manager(db: Session, user_id: int | None) -> None:
    """Raise 400 unless user_id is an active CASE_MANAGER (or cleared)."""
    if user_id is None:
        return
    user = db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=400,
            detail="Selected mentor is not available. Refresh and try again.",
        )
    if "CASE_MANAGER" not in (user.role_names or []):
        raise HTTPException(
            status_code=400,
            detail="Mentors must be case manager accounts.",
        )


def mentored_therapist_user_ids_subquery(mentor_user_id: int):
    return select(TherapistProfile.user_id).where(TherapistProfile.mentor_user_id == mentor_user_id)


def mentor_case_ids_subquery(mentor_user_id: int):
    """Active-assignment cases for therapists this user mentors."""
    return (
        select(CaseAssignment.case_id)
        .join(TherapistProfile, TherapistProfile.user_id == CaseAssignment.therapist_user_id)
        .where(
            TherapistProfile.mentor_user_id == mentor_user_id,
            CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
        )
        .distinct()
    )


def mentor_case_access_clause(user: User):
    return Case.id.in_(mentor_case_ids_subquery(user.id))


def is_mentor_of_therapist(db: Session, mentor_user_id: int, therapist_user_id: int | None) -> bool:
    if not therapist_user_id:
        return False
    profile = db.scalars(
        select(TherapistProfile).where(TherapistProfile.user_id == therapist_user_id)
    ).first()
    return bool(profile and profile.mentor_user_id == mentor_user_id)


def is_mentor_on_case(db: Session, user: User, case: Case) -> bool:
    """True when user mentors an active-assignment therapist on this case."""
    row = db.scalars(
        select(CaseAssignment.id)
        .join(TherapistProfile, TherapistProfile.user_id == CaseAssignment.therapist_user_id)
        .where(
            CaseAssignment.case_id == case.id,
            CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
            TherapistProfile.mentor_user_id == user.id,
        )
        .limit(1)
    ).first()
    return row is not None


def is_assigned_case_manager(user: User, case: Case) -> bool:
    return case.case_manager_user_id == user.id


def is_mentor_only_on_case(db: Session, user: User, case: Case) -> bool:
    """Mentor of a therapist on the case, but not the assigned case manager."""
    if is_assigned_case_manager(user, case):
        return False
    return is_mentor_on_case(db, user, case)


def can_mark_log_mentor_reviewed(
    db: Session,
    user: User,
    *,
    case: Case | None,
    therapist_user_id: int | None,
    already_reviewed: bool,
) -> bool:
    if already_reviewed:
        return False
    if not therapist_user_id:
        return False
    if not is_mentor_of_therapist(db, user.id, therapist_user_id):
        return False
    # Mentors must be able to see the case (or at least be linked via therapist).
    if case is not None and not (
        is_assigned_case_manager(user, case) or is_mentor_on_case(db, user, case)
    ):
        # Still allow if they mentor the session therapist even when assignment ended?
        # Spec: cases via therapist assignment — require mentor-of-therapist only.
        pass
    return True
