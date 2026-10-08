from __future__ import annotations

from types import SimpleNamespace

from app.services.parent_notification_preferences import (
    PARENT_LOG_LEAVE_EMAILS_KEY,
    apply_parent_email_preferences,
    apply_parent_log_leave_emails,
    parent_should_receive_email,
    parent_wants_email,
    read_parent_email_preferences,
    read_parent_log_leave_emails,
)


def _user(**prefs) -> SimpleNamespace:
    return SimpleNamespace(notification_preferences=prefs, role_names=["PARENT"])


def test_parent_email_prefs_default_care_and_billing_on():
    user = _user()
    prefs = read_parent_email_preferences(user)
    assert prefs == {
        "session_logs": True,
        "therapist_leave": True,
        "appointments": True,
        "billing": True,
        "reports": True,
        "meetings": True,
        "incidents": True,
    }
    assert read_parent_log_leave_emails(user) is True


def test_legacy_log_leave_off_disables_logs_and_leave_only():
    user = _user(**{PARENT_LOG_LEAVE_EMAILS_KEY: False})
    assert parent_wants_email(user, "session_logs") is False
    assert parent_wants_email(user, "therapist_leave") is False
    assert parent_wants_email(user, "appointments") is True


def test_granular_email_preferences_can_be_updated():
    user = _user()
    apply_parent_email_preferences(
        user,
        {"appointments": False, "billing": False},
    )
    assert parent_wants_email(user, "appointments") is False
    assert parent_wants_email(user, "billing") is False
    assert parent_wants_email(user, "session_logs") is True


def test_new_keys_override_legacy_log_leave_off():
    user = _user(**{PARENT_LOG_LEAVE_EMAILS_KEY: False, "email_session_logs": True})
    assert parent_wants_email(user, "session_logs") is True
    assert parent_wants_email(user, "therapist_leave") is False


def test_apply_parent_log_leave_emails_sets_both_categories():
    user = _user()
    apply_parent_log_leave_emails(user, False)
    assert parent_wants_email(user, "session_logs") is False
    assert parent_wants_email(user, "therapist_leave") is False
    apply_parent_log_leave_emails(user, True)
    assert read_parent_log_leave_emails(user) is True


def test_staff_meeting_emails_ignore_parent_opt_out():
    user = SimpleNamespace(
        notification_preferences={"email_meetings": False},
        role_names=["CASE_MANAGER"],
    )
    assert parent_should_receive_email(user, "meetings") is True
