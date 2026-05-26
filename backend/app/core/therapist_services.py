"""Therapist service categories — DB-backed with static fallback."""

from __future__ import annotations

from sqlalchemy.orm import Session

SERVICE_CATEGORIES: list[dict[str, str]] = [
    {"id": "shadow_support", "label": "Shadow support"},
    {"id": "homecare", "label": "Homecare"},
    {"id": "occupational_therapy", "label": "Occupational therapy"},
    {"id": "speech_therapy", "label": "Speech therapy"},
    {"id": "special_educator", "label": "Special educator"},
    {"id": "behavior_therapy", "label": "Behavior therapy"},
    {"id": "play_therapy", "label": "Play therapy"},
    {"id": "customised_employment", "label": "Customised employment"},
    {"id": "subject_tutor", "label": "Subject tutor"},
    {"id": "sports", "label": "Sports"},
    {"id": "counselling", "label": "Counselling"},
]

VALID_SERVICE_IDS = {s["id"] for s in SERVICE_CATEGORIES}


def get_service_categories(db: Session) -> list[dict[str, str]]:
    """Return active service categories from DB, falling back to the static list."""
    try:
        from sqlalchemy import select, inspect as sa_inspect
        from app.models.service_category import ServiceCategory

        engine = db.get_bind()
        insp = sa_inspect(engine)
        if not insp.has_table("service_categories"):
            return list(SERVICE_CATEGORIES)

        rows = db.scalars(
            select(ServiceCategory)
            .where(ServiceCategory.is_active.is_(True))
            .order_by(ServiceCategory.sort_order, ServiceCategory.label)
        ).all()
        if not rows:
            return list(SERVICE_CATEGORIES)
        from app.core.service_access import normalize_service_id

        return [{"id": normalize_service_id(r.id), "label": r.label} for r in rows]
    except Exception:
        return list(SERVICE_CATEGORIES)


def validate_service_ids(service_ids: list[str], db: Session | None = None) -> list[str]:
    if db is not None:
        valid = {s["id"] for s in get_service_categories(db)}
    else:
        valid = VALID_SERVICE_IDS
    invalid = [s for s in service_ids if s not in valid]
    if invalid:
        raise ValueError(f"Unknown service categories: {', '.join(invalid)}")
    return list(dict.fromkeys(service_ids))
