"""Allow-listed integration information areas, token lifetimes, and webhook events."""
from __future__ import annotations

from dataclasses import dataclass

from app.models.integration import INTEGRATION_SCOPES
from app.services.integration.errors import ValidationError

ACCESS_TOKEN_MINUTES = frozenset({15, 60, 480, 1440})
KEY_TTL_DAYS = frozenset({0, 30, 90, 365})

WEBHOOK_EVENTS = frozenset(
    {
        "case.updated",
        "session.logged",
        "report.draft_ready",
        "goal.pending_review",
        "iep.updated",
        "reporting.overdue",
        "incident.reported",
    }
)

SIGNAL_KEYS: dict[str, frozenset[str]] = {
    "cases": frozenset({"environment_factor", "support_need", "participation"}),
    "sessions": frozenset({"progress_signal", "strategy_effectiveness", "participation"}),
    "goals": frozenset({"outcome_rating", "confidence", "frequency"}),
}

DOMAIN_WRITE_SCOPE = {
    "cases": "cases:write",
    "sessions": "sessions:write",
    "goals": "goals:write",
}


@dataclass(frozen=True)
class InfoDomain:
    id: str
    read_scope: str
    write_scope: str | None


INFO_DOMAINS: tuple[InfoDomain, ...] = (
    InfoDomain("cases", "cases:read", "cases:write"),
    InfoDomain("sessions", "sessions:summarize", "sessions:write"),
    InfoDomain("reports", "reports:read", None),
    InfoDomain("goals", "goals:read", "goals:write"),
    InfoDomain("iep", "iep:read", None),
    InfoDomain("reporting", "reporting:pending", None),
    InfoDomain("ops", "ops:summary", None),
    InfoDomain("profiles", "profiles:read", "profiles:write"),
    InfoDomain("finance", "finance:read", None),
)

_DOMAIN_BY_ID = {domain.id: domain for domain in INFO_DOMAINS}


def build_scopes(*, allow_read: bool, allow_write: bool, info_access: list[str]) -> list[str]:
    if not allow_read and not allow_write:
        raise ValidationError("Turn on Read or Write before saving this key.")
    if not info_access:
        raise ValidationError("Choose at least one kind of information this key can use.")
    unknown = [item for item in info_access if item not in _DOMAIN_BY_ID]
    if unknown:
        raise ValidationError("One of those information areas is not available.")
    selected = set(info_access)
    scopes: list[str] = []
    for domain in INFO_DOMAINS:
        if domain.id not in selected:
            continue
        if allow_read:
            scopes.append(domain.read_scope)
        if allow_write and domain.write_scope:
            scopes.append(domain.write_scope)
    if not scopes:
        raise ValidationError(
            "Those areas stay read-only. Turn Read on, or choose Cases, Sessions, Goals, or Therapist profiles while Write is on."
        )
    illegal = [scope for scope in scopes if scope not in INTEGRATION_SCOPES]
    if illegal:
        raise ValidationError("One of those scopes is not available.")
    return scopes


def describe_scopes(scopes: list[str]) -> dict:
    present = set(scopes or [])
    info_access: list[str] = []
    allow_read = False
    allow_write = False
    for domain in INFO_DOMAINS:
        read_on = domain.read_scope in present
        write_on = bool(domain.write_scope and domain.write_scope in present)
        if read_on or write_on:
            info_access.append(domain.id)
        allow_read = allow_read or read_on
        allow_write = allow_write or write_on
    return {"allow_read": allow_read, "allow_write": allow_write, "info_access": info_access}


def normalize_access_token_minutes(minutes: int | None, *, fallback: int) -> int:
    if minutes is None:
        return fallback if fallback in ACCESS_TOKEN_MINUTES else 15
    if int(minutes) not in ACCESS_TOKEN_MINUTES:
        raise ValidationError("Choose how long each access token stays valid.")
    return int(minutes)


def normalize_key_ttl_days(days: int | None, *, fallback: int) -> int:
    if days is None:
        return fallback if fallback in KEY_TTL_DAYS else 365
    if int(days) not in KEY_TTL_DAYS:
        raise ValidationError("Choose how long this API key stays valid.")
    return int(days)


def normalize_webhook_events(events: list[str] | None) -> list[str]:
    if not events:
        raise ValidationError("Choose at least one event to send.")
    cleaned: list[str] = []
    for raw in events:
        event = str(raw).strip()
        if event not in WEBHOOK_EVENTS:
            raise ValidationError("One of those events is not available.")
        if event not in cleaned:
            cleaned.append(event)
    return cleaned
