"""Defaults for session venue (HOME / SCHOOL) based on case product module."""
from __future__ import annotations

from app.models.session import SessionMode


def is_school_default_module(product_module: str | None) -> bool:
    """Shadow support and B2B cases default to school venue."""
    token = (product_module or "").strip().lower()
    return "shadow" in token or token == "b2b" or "b2b" in token


def default_session_mode_for_case(case) -> SessionMode:
    """Return SCHOOL for shadow/b2b cases, otherwise HOME."""
    if case is None:
        return SessionMode.HOME
    if is_school_default_module(getattr(case, "product_module", None)):
        return SessionMode.SCHOOL
    return SessionMode.HOME


def default_service_location_type(product_module: str | None) -> str:
    """Case-level service location type string used by the allotment wizard."""
    return "school" if is_school_default_module(product_module) else "home"
