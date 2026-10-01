from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.permissions import RoleName
from app.models.user import User
from app.services.therapist_profile_quality import evaluate_profile_quality
from app.services.therapist_profile_service import get_or_create_profile


def compute_profile_completion(user: User, profile) -> dict:
    quality = evaluate_profile_quality(user, profile)
    missing = [item["key"] for item in quality["items"] if not item["passed"]]
    done = len(quality["items"]) - len(missing)
    total = len(quality["items"])
    complete = len(missing) == 0
    submitted = getattr(profile, "submitted_at", None) is not None
    return {
        "percent": quality["percent"],
        "complete": complete,
        "missing_fields": missing,
        "total_steps": total,
        "completed_steps": done,
        "needs_nudge": (not complete) and (not submitted),
        "quality": quality,
    }


def completion_for_therapist_user(db: Session, user: User) -> dict | None:
    if RoleName.THERAPIST.value not in user.role_names:
        return None
    profile = get_or_create_profile(db, user.id)
    return compute_profile_completion(user, profile)
