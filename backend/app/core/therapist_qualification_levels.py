from __future__ import annotations

from typing import Optional

# Ordered low → high for UI; therapists pick highest level only.
QUALIFICATION_LEVELS: tuple[tuple[str, str], ...] = (
    ("DIPLOMA", "Diploma"),
    ("UG", "UG (Bachelor's)"),
    ("PG", "PG (Master's)"),
    ("M_PHIL", "M.Phil"),
    ("PHD", "PhD / Doctorate"),
    ("PROFESSIONAL_REGISTRATION", "Professional registration (e.g. RCI)"),
    ("OTHER", "Other"),
)

VALID_QUALIFICATION_LEVEL_CODES = frozenset(code for code, _ in QUALIFICATION_LEVELS)

QUALIFICATION_LEVEL_LABELS = dict(QUALIFICATION_LEVELS)


def normalize_qualification_level(value: object | None) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, str):
        return None
    code = value.strip().upper()
    if not code:
        return None
    if code not in VALID_QUALIFICATION_LEVEL_CODES:
        return None
    return code


def qualification_level_label(code: str | None) -> str | None:
    if not code:
        return None
    return QUALIFICATION_LEVEL_LABELS.get(code.upper())
