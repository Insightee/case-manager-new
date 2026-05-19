"""Therapist service categories for public profiles."""

from __future__ import annotations

SERVICE_CATEGORIES: list[dict[str, str]] = [
    {"id": "shadow", "label": "Shadow support"},
    {"id": "homecare", "label": "Homecare"},
    {"id": "occupational_therapy", "label": "Occupational therapy"},
    {"id": "speech_therapy", "label": "Speech therapy"},
    {"id": "special_educator", "label": "Special educator"},
    {"id": "behavior_therapy", "label": "Behavior therapy"},
    {"id": "play_therapy", "label": "Play therapy"},
    {"id": "customised_employment", "label": "Customised employment"},
    {"id": "subject_tutor", "label": "Subject tutor"},
    {"id": "sports", "label": "Sports"},
]

VALID_SERVICE_IDS = {s["id"] for s in SERVICE_CATEGORIES}


def validate_service_ids(service_ids: list[str]) -> list[str]:
    invalid = [s for s in service_ids if s not in VALID_SERVICE_IDS]
    if invalid:
        raise ValueError(f"Unknown service categories: {', '.join(invalid)}")
    return list(dict.fromkeys(service_ids))
