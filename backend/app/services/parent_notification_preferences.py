from __future__ import annotations

from typing import Literal

from app.core.permissions import RoleName
from app.models.user import User

# Legacy single toggle (session logs + leave only)
PARENT_LOG_LEAVE_EMAILS_KEY = "parent_log_leave_emails"

ParentEmailCategory = Literal[
    "session_logs",
    "therapist_leave",
    "appointments",
    "billing",
    "reports",
    "meetings",
]

PARENT_EMAIL_CATEGORIES: tuple[ParentEmailCategory, ...] = (
    "session_logs",
    "therapist_leave",
    "appointments",
    "billing",
    "reports",
    "meetings",
)

CATEGORY_STORAGE_KEYS: dict[ParentEmailCategory, str] = {
    "session_logs": "email_session_logs",
    "therapist_leave": "email_therapist_leave",
    "appointments": "email_appointments",
    "billing": "email_billing",
    "reports": "email_reports",
    "meetings": "email_meetings",
}

# New parents: email on for care + billing + meetings; scheduling/report digests opt-in.
DEFAULT_EMAIL_ON: frozenset[ParentEmailCategory] = frozenset(
    {"session_logs", "therapist_leave", "billing", "meetings"}
)


def _coerce_enabled(value: object | None, *, default: bool = True) -> bool:
    if value is True:
        return True
    if value is False:
        return False
    if isinstance(value, str) and value.strip().lower() in {"0", "false", "no", "off"}:
        return False
    if value is None:
        return default
    return bool(value)


def _legacy_log_leave_disabled(prefs: dict) -> bool:
    legacy = prefs.get(PARENT_LOG_LEAVE_EMAILS_KEY)
    if legacy is False:
        return True
    if isinstance(legacy, str) and legacy.strip().lower() in {"0", "false", "no", "off"}:
        return True
    return False


def _category_default(prefs: dict, category: ParentEmailCategory) -> bool:
    storage_key = CATEGORY_STORAGE_KEYS[category]
    default_on = category in DEFAULT_EMAIL_ON
    if storage_key in prefs:
        return _coerce_enabled(prefs.get(storage_key), default=default_on)
    if category in ("session_logs", "therapist_leave") and _legacy_log_leave_disabled(prefs):
        return False
    return default_on


def parent_wants_email(user: User | None, category: ParentEmailCategory) -> bool:
    """Parents opt out per category via profile; default is to receive emails."""
    if user is None:
        return False
    prefs = user.notification_preferences if isinstance(user.notification_preferences, dict) else {}
    return _category_default(prefs, category)


def parent_wants_log_leave_emails(user: User | None) -> bool:
    """Backward-compatible helper: both session logs and leave must be enabled."""
    return parent_wants_email(user, "session_logs") and parent_wants_email(user, "therapist_leave")


def read_parent_email_preferences(user: User) -> dict[str, bool]:
    prefs = user.notification_preferences if isinstance(user.notification_preferences, dict) else {}
    return {category: _category_default(prefs, category) for category in PARENT_EMAIL_CATEGORIES}


def apply_parent_email_preferences(user: User, updates: dict[str, bool | None]) -> None:
    stored = dict(user.notification_preferences or {})
    for category in PARENT_EMAIL_CATEGORIES:
        if category not in updates or updates[category] is None:
            continue
        stored[CATEGORY_STORAGE_KEYS[category]] = bool(updates[category])
    user.notification_preferences = stored


def parent_should_receive_email(user: User | None, category: ParentEmailCategory) -> bool:
    """Apply parent opt-out only for parent-role users; staff always receive."""
    if user is None:
        return False
    if RoleName.PARENT.value not in user.role_names:
        return True
    return parent_wants_email(user, category)


def read_parent_log_leave_emails(user: User) -> bool:
    prefs = read_parent_email_preferences(user)
    return prefs["session_logs"] and prefs["therapist_leave"]


def apply_parent_log_leave_emails(user: User, enabled: bool) -> None:
    apply_parent_email_preferences(
        user,
        {"session_logs": enabled, "therapist_leave": enabled},
    )
