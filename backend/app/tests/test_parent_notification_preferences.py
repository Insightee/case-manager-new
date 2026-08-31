from __future__ import annotations

from types import SimpleNamespace

from app.services.parent_notification_preferences import (
    apply_parent_log_leave_emails,
    parent_wants_log_leave_emails,
    read_parent_log_leave_emails,
)


def test_parent_log_leave_email_pref_defaults_to_true():
    user = SimpleNamespace(notification_preferences={})
    assert parent_wants_log_leave_emails(user) is True
    assert read_parent_log_leave_emails(user) is True


def test_parent_log_leave_email_pref_can_opt_out_and_back_in():
    user = SimpleNamespace(notification_preferences={})
    apply_parent_log_leave_emails(user, False)
    assert parent_wants_log_leave_emails(user) is False
    apply_parent_log_leave_emails(user, True)
    assert parent_wants_log_leave_emails(user) is True
