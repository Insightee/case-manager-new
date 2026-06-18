"""Bulk update therapist primary CM and active case CMs from CSV rows."""
from __future__ import annotations

from typing import Literal, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.assignment import CaseAssignment, CaseAssignmentStatus
from app.models.case import Case, CaseStatus
from app.models.therapist_profile import TherapistProfile
from app.models.user import User

CM_ROLE_NAMES = frozenset({"CASE_MANAGER", "MODULE_ADMIN", "ADMIN", "SUPER_ADMIN"})

RowStatus = Literal["unchanged", "will_update", "updated", "failed"]


def _normalize_email(value: str | None) -> str | None:
    text = (value or "").strip().lower()
    return text or None


def _normalize_id(value: str | None) -> str | None:
    text = (value or "").strip()
    if not text or text in {"—", "-"}:
        return None
    return text


def _normalize_name(value: str | None) -> str:
    return (value or "").strip().lower()


def _resolve_therapist(
    db: Session,
    *,
    therapist_id: str | None,
    email: str | None,
) -> tuple[User | None, str | None]:
    email_norm = _normalize_email(email)
    id_norm = _normalize_id(therapist_id)

    if not email_norm and not id_norm:
        return None, "Provide therapist email or Therapist ID"

    by_email: User | None = None
    if email_norm:
        by_email = db.scalars(select(User).where(func.lower(User.email) == email_norm)).first()
        if by_email and "THERAPIST" not in (by_email.role_names or []):
            return None, "Email belongs to a non-therapist user"

    by_id: User | None = None
    if id_norm:
        by_id = db.scalars(select(User).where(User.external_employee_id == id_norm)).first()
        if by_id and "THERAPIST" not in (by_id.role_names or []):
            return None, "Therapist ID belongs to a non-therapist user"

    if by_email and by_id and by_email.id != by_id.id:
        return None, "Email and Therapist ID refer to different therapists"

    therapist = by_email or by_id
    if not therapist:
        return None, "Therapist not found"
    return therapist, None


def _resolve_case_manager(db: Session, email: str | None) -> tuple[User | None, str | None]:
    email_norm = _normalize_email(email)
    if not email_norm:
        return None, "Case Manager Email is required"

    cm = db.scalars(select(User).where(func.lower(User.email) == email_norm)).first()
    if not cm:
        return None, f"Case manager not found: {email_norm}"
    if not cm.is_active:
        return None, f"Case manager account is inactive: {email_norm}"
    role_names = {str(r).upper() for r in (cm.role_names or [])}
    if not role_names & CM_ROLE_NAMES:
        return None, f"User cannot be a case manager: {email_norm}"
    return cm, None


def _active_case_ids_for_therapist(db: Session, therapist_user_id: int) -> list[int]:
    stmt = (
        select(Case.id)
        .join(CaseAssignment, CaseAssignment.case_id == Case.id)
        .where(
            CaseAssignment.therapist_user_id == therapist_user_id,
            CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
            Case.status == CaseStatus.ACTIVE,
        )
        .distinct()
        .order_by(Case.id)
    )
    return list(db.scalars(stmt).all())


def _current_cm_email(db: Session, user_id: int | None) -> str | None:
    if not user_id:
        return None
    user = db.get(User, user_id)
    return user.email if user else None


def _primary_cm_name_warning(written_name: str | None, resolved_cm: User) -> str | None:
    written = (written_name or "").strip()
    if not written:
        return None
    actual = (resolved_cm.full_name or resolved_cm.email or "").strip()
    if _normalize_name(written) == _normalize_name(actual):
        return None
    return f"Primary CM name '{written}' does not match '{actual}'"


def process_bulk_primary_cm_rows(
    db: Session,
    rows: list[dict],
    *,
    apply: bool,
) -> dict:
    results: list[dict] = []
    seen_therapist_keys: set[str] = set()
    summary = {"unchanged": 0, "will_update": 0, "updated": 0, "failed": 0}

    for index, row in enumerate(rows, start=1):
        therapist_id = row.get("therapist_id")
        email = row.get("email")
        primary_cm_name = row.get("primary_cm_name")
        case_manager_email = row.get("case_manager_email")

        base = {
            "row_index": index,
            "therapist_email": _normalize_email(email),
            "therapist_id": _normalize_id(therapist_id),
            "case_manager_email": _normalize_email(case_manager_email) or (case_manager_email or "").strip(),
            "primary_cm_name": (primary_cm_name or "").strip() or None,
            "warning": None,
            "message": None,
            "profile_updated": False,
            "cases_updated": 0,
            "old_cm_email": None,
            "new_cm_email": None,
        }

        therapist, therapist_error = _resolve_therapist(db, therapist_id=therapist_id, email=email)
        if therapist_error:
            results.append({**base, "status": "failed", "message": therapist_error})
            summary["failed"] += 1
            continue

        dedupe_key = f"user:{therapist.id}"
        if dedupe_key in seen_therapist_keys:
            results.append({**base, "status": "failed", "message": "Duplicate therapist row in upload"})
            summary["failed"] += 1
            continue
        seen_therapist_keys.add(dedupe_key)

        base["therapist_email"] = therapist.email
        base["therapist_id"] = therapist.external_employee_id

        cm, cm_error = _resolve_case_manager(db, case_manager_email)
        if cm_error:
            results.append({**base, "status": "failed", "message": cm_error})
            summary["failed"] += 1
            continue

        warning = _primary_cm_name_warning(primary_cm_name, cm)
        if warning:
            base["warning"] = warning

        profile = db.scalars(
            select(TherapistProfile).where(TherapistProfile.user_id == therapist.id)
        ).first()
        if not profile:
            results.append({**base, "status": "failed", "message": "Therapist profile not found"})
            summary["failed"] += 1
            continue

        case_ids = _active_case_ids_for_therapist(db, therapist.id)
        old_cm_email = _current_cm_email(db, profile.supervisor_user_id)
        new_cm_email = cm.email
        base["old_cm_email"] = old_cm_email
        base["new_cm_email"] = new_cm_email

        profile_needs_update = profile.supervisor_user_id != cm.id
        cases_to_update: list[Case] = []
        for case_id in case_ids:
            case = db.get(Case, case_id)
            if case and case.case_manager_user_id != cm.id:
                cases_to_update.append(case)

        if not profile_needs_update and not cases_to_update:
            results.append({**base, "status": "unchanged", "message": "Case manager already matches"})
            summary["unchanged"] += 1
            continue

        if not apply:
            results.append(
                {
                    **base,
                    "status": "will_update",
                    "message": (
                        f"Will update profile"
                        f"{'' if profile_needs_update else ' (unchanged)'}"
                        f" and {len(cases_to_update)} active case(s)"
                    ),
                    "profile_updated": profile_needs_update,
                    "cases_updated": len(cases_to_update),
                }
            )
            summary["will_update"] += 1
            continue

        if profile_needs_update:
            profile.supervisor_user_id = cm.id
            base["profile_updated"] = True

        updated_cases = 0
        for case in cases_to_update:
            case.case_manager_user_id = cm.id
            updated_cases += 1
        base["cases_updated"] = updated_cases

        results.append(
            {
                **base,
                "status": "updated",
                "message": (
                    f"Updated profile"
                    f"{'' if base['profile_updated'] else ' (unchanged)'}"
                    f" and {updated_cases} active case(s)"
                ),
            }
        )
        summary["updated"] += 1

    if apply and summary["updated"] > 0:
        db.flush()

    return {
        "apply": apply,
        "summary": summary,
        "results": results,
    }
