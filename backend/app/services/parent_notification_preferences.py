from __future__ import annotations

from app.models.user import User

PARENT_LOG_LEAVE_EMAILS_KEY = "parent_log_leave_emails"


def parent_wants_log_leave_emails(user: User | None) -> bool:
    """Parents opt out via profile; default is to receive operational emails."""
    if user is None:
        return False
    prefs = user.notification_preferences if isinstance(user.notification_preferences, dict) else {}
    value = prefs.get(PARENT_LOG_LEAVE_EMAILS_KEY, True)
    if value is False:
        return False
    if isinstance(value, str) and value.strip().lower() in {"0", "false", "no", "off"}:
        return False
    return True


def read_parent_log_leave_emails(user: User) -> bool:
    return parent_wants_log_leave_emails(user)


def apply_parent_log_leave_emails(user: User, enabled: bool) -> None:
    prefs = dict(user.notification_preferences or {})
    prefs[PARENT_LOG_LEAVE_EMAILS_KEY] = bool(enabled)
    user.notification_preferences = prefs
