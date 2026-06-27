"""Resolve normalized clinical service category for session caps and auto-close."""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy.orm import Session

from app.core.service_access import normalize_service_id, parent_service_id_for_product_module

# Canonical categories used by session auto-close rules.
CANONICAL_CATEGORIES = frozenset(
    {
        "shadow_support",
        "school_support",
        "homecare",
        "special_education",
        "behavior_therapy",
        "play_therapy",
        "counselling",
        "other_clinical",
        "unknown",
    }
)

_SHADOW_ALIASES = frozenset(
    {
        "shadow",
        "shadow_support",
        "shadow support",
        "shadow-support",
        "school_shadow",
        "school shadow",
    }
)

_SCHOOL_SUPPORT_ALIASES = frozenset(
    {
        "school_support",
        "school support",
        "school-support",
        "lsa",
        "learning_support_assistant",
        "learning support assistant",
    }
)

_HOMECARE_ALIASES = frozenset(
    {
        "homecare",
        "home_care",
        "home care",
        "home-care",
        "home_therapy",
        "home therapy",
    }
)

_SPECIAL_ED_ALIASES = frozenset(
    {
        "special_education",
        "special_educator",
        "special educator",
        "special-educator",
        "special_ed",
    }
)

_BEHAVIOR_ALIASES = frozenset(
    {
        "behavior_therapy",
        "behaviour_therapy",
        "behavior therapy",
        "behaviour therapy",
    }
)

_PLAY_ALIASES = frozenset(
    {
        "play_therapy",
        "play therapy",
    }
)

_COUNSELLING_ALIASES = frozenset(
    {
        "counselling",
        "counseling",
        "counselling_session",
        "counseling_session",
    }
)

_OTHER_CLINICAL_IDS = frozenset(
    {
        "occupational_therapy",
        "speech_therapy",
        "customised_employment",
        "subject_tutor",
        "sports",
    }
)


def _slugify(raw: str | None) -> str:
    text = (raw or "").strip().lower()
    text = re.sub(r"[\s\-]+", "_", text)
    text = re.sub(r"[^a-z0-9_]", "", text)
    return text


def normalize_clinical_token(raw: str | None) -> str:
    """Lowercase slug; map known aliases to canonical session-cap category."""
    if not raw:
        return "unknown"
    slug = _slugify(raw)
    if not slug:
        return "unknown"
    compact = slug.replace("_", " ")
    for alias in _SHADOW_ALIASES:
        if slug == _slugify(alias) or compact == alias.replace("_", " "):
            return "shadow_support"
    for alias in _SCHOOL_SUPPORT_ALIASES:
        if slug == _slugify(alias) or compact == alias.replace("_", " "):
            return "school_support"
    for alias in _HOMECARE_ALIASES:
        if slug == _slugify(alias) or compact == alias.replace("_", " "):
            return "homecare"
    for alias in _SPECIAL_ED_ALIASES:
        if slug == _slugify(alias) or compact == alias.replace("_", " "):
            return "special_education"
    for alias in _BEHAVIOR_ALIASES:
        if slug == _slugify(alias) or compact == alias.replace("_", " "):
            return "behavior_therapy"
    for alias in _PLAY_ALIASES:
        if slug == _slugify(alias) or compact == alias.replace("_", " "):
            return "play_therapy"
    for alias in _COUNSELLING_ALIASES:
        if slug == _slugify(alias) or compact == alias.replace("_", " "):
            return "counselling"
    if slug in CANONICAL_CATEGORIES:
        return slug
    if slug in _OTHER_CLINICAL_IDS:
        return "other_clinical"
    return "other_clinical"


def _active_case_service_key(case: Any) -> str | None:
    services = getattr(case, "services", None) or []
    for svc in services:
        status = getattr(svc, "status", None)
        status_val = status.value if hasattr(status, "value") else str(status or "")
        if status_val.upper() == "ACTIVE":
            key = getattr(svc, "service_key", None)
            if key:
                return str(key)
    return None


def resolve_clinical_service_category(
    case: Any,
    *,
    db: Session | None = None,
    product_module: str | None = None,
) -> str:
    """
    Resolve case/session service line to a canonical auto-close category.
    Uses product_module, service_type, active case service, and DB category mapping.
    """
    tokens: list[str] = []
    if product_module:
        tokens.append(str(product_module))
    if case is not None:
        pm = getattr(case, "product_module", None)
        if pm:
            tokens.append(str(pm))
        st = getattr(case, "service_type", None)
        if st:
            tokens.append(str(st))
        svc_key = _active_case_service_key(case)
        if svc_key:
            tokens.append(svc_key)
        if db is not None and pm:
            parent = parent_service_id_for_product_module(db, str(pm))
            if parent:
                tokens.append(parent)

    if not tokens:
        return "unknown"

    # Prefer product_module token first, then enrich with others.
    primary = normalize_clinical_token(tokens[0])
    if primary not in ("unknown", "other_clinical"):
        return primary
    for token in tokens[1:]:
        cat = normalize_clinical_token(token)
        if cat not in ("unknown", "other_clinical"):
            return cat
    return primary


def product_module_for_case(case: Any, *, db: Session | None = None) -> str:
    """Backward-compatible module string for callers expecting product_module slug."""
    if case is None:
        return "unknown"
    raw = getattr(case, "product_module", None) or "unknown"
    return normalize_service_id(str(raw))


def resolved_category_for_case(case: Any, *, db: Session | None = None) -> str:
    return resolve_clinical_service_category(case, db=db)
