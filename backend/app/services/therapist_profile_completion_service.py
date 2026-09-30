from __future__ import annotations

from typing import Callable

from sqlalchemy.orm import Session

from app.core.permissions import RoleName
from app.core.therapist_qualification_levels import normalize_qualification_level
from app.models.therapist_profile import TherapistProfile
from app.models.user import User
from app.services.therapist_profile_service import SNAPSHOT_FIELDS, get_or_create_profile

CompletionItem = tuple[str, Callable[[], bool]]


def _effective_listing(profile: TherapistProfile) -> dict:
    data = {
        "display_name": profile.display_name,
        "short_bio": profile.short_bio,
        "services_offered": list(profile.services_offered or []),
    }
    pending = profile.pending_submission
    if pending:
        for key in SNAPSHOT_FIELDS:
            if key in pending:
                data[key] = pending[key]
    return data


def _home_address_complete(user: User) -> bool:
    line1 = (user.home_address_line1 or "").strip()
    city = (user.home_city or "").strip()
    return bool(line1 and city)


def _full_name_complete(user: User) -> bool:
    return bool((user.full_name or "").strip())


def _phone_complete(user: User) -> bool:
    return bool((user.phone or "").strip())


def _avatar_complete(user: User) -> bool:
    return bool((user.avatar_path or "").strip())


def _display_name_complete(user: User, listing: dict) -> bool:
    display = (listing.get("display_name") or "").strip()
    if display:
        return True
    return _full_name_complete(user)


def _short_bio_complete(listing: dict) -> bool:
    return bool((listing.get("short_bio") or "").strip())


def _qualification_level_complete(profile: TherapistProfile) -> bool:
    level = profile.academic_qualification_level
    pending = profile.pending_submission
    if pending and "academic_qualification_level" in pending:
        level = pending.get("academic_qualification_level")
    return normalize_qualification_level(level) is not None


def _services_complete(listing: dict) -> bool:
    services = listing.get("services_offered") or []
    return len(services) > 0


def build_completion_items(user: User, profile: TherapistProfile) -> list[CompletionItem]:
    listing = _effective_listing(profile)
    items: list[CompletionItem] = [
        ("full_name", lambda: _full_name_complete(user)),
        ("phone", lambda: _phone_complete(user)),
        ("home_address", lambda: _home_address_complete(user)),
        ("avatar", lambda: _avatar_complete(user)),
        ("display_name", lambda: _display_name_complete(user, listing)),
        ("short_bio", lambda: _short_bio_complete(listing)),
        ("qualification_level", lambda: _qualification_level_complete(profile)),
    ]
    if not _services_complete(listing):
        items.append(("services_offered", lambda: _services_complete(listing)))
    return items


def compute_profile_completion(user: User, profile: TherapistProfile) -> dict:
    items = build_completion_items(user, profile)
    missing = [key for key, check in items if not check()]
    done = len(items) - len(missing)
    total = len(items)
    percent = round(100 * done / total) if total else 100
    complete = len(missing) == 0
    return {"percent": percent, "complete": complete, "missing_fields": missing}


def completion_for_therapist_user(db: Session, user: User) -> dict | None:
    if RoleName.THERAPIST.value not in user.role_names:
        return None
    profile = get_or_create_profile(db, user.id)
    return compute_profile_completion(user, profile)
