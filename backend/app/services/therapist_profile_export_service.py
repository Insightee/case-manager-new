"""CSV export of therapist service profiles for the admin Service profiles page."""
from __future__ import annotations

import csv
import io
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.therapist_services import get_service_categories
from app.models.therapist_profile import TherapistProfile, TherapistProfileStatus
from app.models.user import User
from app.services.therapist_profile_service import has_pending_submission, list_profiles

MAX_EXPORT_ROWS = 5000

EXPORT_HEADERS: list[tuple[str, str]] = [
    ("External employee ID", "external_employee_id"),
    ("Full name", "full_name"),
    ("Display name", "display_name"),
    ("Email", "email"),
    ("Phone", "phone"),
    ("Start date", "start_date"),
    ("Services", "services"),
    ("Pending changes", "pending_changes"),
    ("Short bio", "short_bio"),
    ("Qualifications", "qualifications"),
    ("Primary case manager", "primary_case_manager"),
    ("Mentor", "mentor"),
    ("Region", "region"),
]


def _service_labels(service_ids: list[str] | None, label_by_id: dict[str, str]) -> str:
    labels = [label_by_id.get(sid, sid.replace("_", " ")) for sid in (service_ids or []) if sid]
    return ", ".join(labels)


def _matches_search(profile: TherapistProfile, user: User, search: str) -> bool:
    q = search.strip().lower()
    if not q:
        return True
    haystack = [
        profile.display_name or "",
        user.full_name or "",
        user.email or "",
    ]
    return any(q in value.lower() for value in haystack if value)


def build_export_rows(
    db: Session,
    *,
    status: TherapistProfileStatus | None = None,
    search: Optional[str] = None,
) -> list[dict[str, str]]:
    categories = get_service_categories(db)
    label_by_id = {c["id"]: c["label"] for c in categories}

    profiles = list_profiles(db, status)
    profile_ids = [p.id for p in profiles]
    if not profile_ids:
        return []

    loaded = db.scalars(
        select(TherapistProfile)
        .where(TherapistProfile.id.in_(profile_ids))
        .options(
            selectinload(TherapistProfile.user),
            selectinload(TherapistProfile.supervisor),
            selectinload(TherapistProfile.mentor),
        )
        .order_by(TherapistProfile.updated_at.desc())
    ).all()
    by_id = {p.id: p for p in loaded}

    rows: list[dict[str, str]] = []
    for profile in profiles:
        full_profile = by_id.get(profile.id)
        if not full_profile:
            continue
        user = full_profile.user
        if not user:
            user = db.get(User, full_profile.user_id)
        if not user:
            continue
        if search and not _matches_search(full_profile, user, search):
            continue
        rows.append(
            {
                "external_employee_id": user.external_employee_id or "",
                "full_name": user.full_name or "",
                "display_name": full_profile.display_name or "",
                "email": user.email or "",
                "phone": user.phone or "",
                "start_date": full_profile.employment_start_date.isoformat()
                if full_profile.employment_start_date
                else "",
                "services": _service_labels(full_profile.services_offered, label_by_id),
                "pending_changes": "Yes" if has_pending_submission(full_profile) else "No",
                "short_bio": full_profile.short_bio or "",
                "qualifications": full_profile.academic_qualifications or "",
                "primary_case_manager": (
                    full_profile.supervisor.full_name if full_profile.supervisor else ""
                ),
                "mentor": full_profile.mentor.full_name if full_profile.mentor else "",
                "region": user.region or "",
            }
        )
    return rows


def export_therapist_profiles_csv(
    db: Session,
    *,
    status: TherapistProfileStatus | None = None,
    search: Optional[str] = None,
) -> str:
    rows = build_export_rows(db, status=status, search=search)
    if len(rows) > MAX_EXPORT_ROWS:
        raise ValueError(f"Export exceeds {MAX_EXPORT_ROWS} rows — narrow your filters and try again.")
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=[header for header, _ in EXPORT_HEADERS])
    writer.writeheader()
    for row in rows:
        writer.writerow({header: row.get(key, "") for header, key in EXPORT_HEADERS})
    return buf.getvalue()
