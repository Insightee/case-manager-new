from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.services.appointment_notification_service import (
    _is_same_day_ist,
    notify_parents_session_cancelled,
    notify_parents_session_rescheduled,
)
from app.services.email.templates import render_template
from app.services.parent_notification_preferences import apply_parent_email_preferences


def test_is_same_day_ist_boundary():
    today = date(2026, 10, 8)
    with patch("app.services.appointment_notification_service.today_ist", return_value=today):
        assert _is_same_day_ist(today) is True
        assert _is_same_day_ist(date(2026, 10, 7)) is False
        assert _is_same_day_ist(date(2026, 10, 7), today) is True


def test_cancel_cleared_case_id_still_notifies_in_app():
    parent = SimpleNamespace(
        id=1,
        email="p@example.com",
        full_name="Parent",
        role_names=["PARENT"],
        notification_preferences={},
    )
    slot = SimpleNamespace(
        id=5,
        case_id=None,
        slot_date=date(2026, 10, 8),
        start_time=SimpleNamespace(strftime=lambda _: "10:00"),
    )
    case = SimpleNamespace(child=SimpleNamespace(full_name="Child"))
    created = []

    class FakeDb:
        def get(self, model, pk):
            if pk == 10:
                return case
            return parent

        def scalars(self, *a, **k):
            class R:
                def first(self_inner):
                    return case

            return R()

    emails: list[str] = []

    with patch(
        "app.services.appointment_notification_service._parent_users_for_case",
        return_value=[parent],
    ), patch(
        "app.services.appointment_notification_service.notification_service.create_notification",
        side_effect=lambda *a, **kw: created.append(kw) or object(),
    ), patch(
        "app.services.appointment_notification_service.send_parent_email",
        side_effect=lambda *a, **kw: emails.append(kw["template_key"]),
    ), patch(
        "app.services.appointment_notification_service.today_ist",
        return_value=date(2026, 10, 8),
    ):
        n = notify_parents_session_cancelled(
            FakeDb(),
            slot,
            case_id=10,
            cancelled_by_name="Therapist",
        )

    assert n == 1
    assert len(created) == 1
    assert emails == ["session_cancelled_today"]


def test_cancel_future_date_no_email():
    parent = SimpleNamespace(
        id=1,
        email="p@example.com",
        full_name="Parent",
        role_names=["PARENT"],
        notification_preferences={},
    )
    slot = SimpleNamespace(
        id=5,
        case_id=None,
        slot_date=date(2026, 10, 15),
        start_time=SimpleNamespace(strftime=lambda _: "10:00"),
    )

    class FakeDb:
        def get(self, model, pk):
            return SimpleNamespace(child=SimpleNamespace(full_name="Child"))

        def scalars(self, *a, **k):
            class R:
                def first(self_inner):
                    return SimpleNamespace(child=SimpleNamespace(full_name="Child"))

            return R()

    emails: list[str] = []

    with patch(
        "app.services.appointment_notification_service._parent_users_for_case",
        return_value=[parent],
    ), patch(
        "app.services.appointment_notification_service.notification_service.create_notification",
    ), patch(
        "app.services.appointment_notification_service.send_parent_email",
        side_effect=lambda *a, **kw: emails.append(1),
    ), patch(
        "app.services.appointment_notification_service.today_ist",
        return_value=date(2026, 10, 8),
    ):
        notify_parents_session_cancelled(FakeDb(), slot, case_id=10, cancelled_by_name="T")

    assert emails == []


def test_reschedule_email_when_new_date_is_today():
    parent = SimpleNamespace(
        id=1,
        email="p@example.com",
        full_name="Parent",
        role_names=["PARENT"],
        notification_preferences={},
    )
    old = SimpleNamespace(
        id=1,
        slot_date=date(2026, 10, 15),
        start_time=SimpleNamespace(strftime=lambda _: "09:00"),
    )
    new = SimpleNamespace(
        id=2,
        slot_date=date(2026, 10, 8),
        start_time=SimpleNamespace(strftime=lambda _: "11:00"),
    )

    class FakeDb:
        def get(self, model, pk):
            return SimpleNamespace(child=SimpleNamespace(full_name="Child"))

    templates: list[str] = []

    with patch(
        "app.services.appointment_notification_service._parent_users_for_case",
        return_value=[parent],
    ), patch(
        "app.services.appointment_notification_service.notification_service.create_notification",
    ), patch(
        "app.services.appointment_notification_service.send_parent_email",
        side_effect=lambda *a, **kw: templates.append(kw["template_key"]),
    ), patch(
        "app.services.appointment_notification_service.today_ist",
        return_value=date(2026, 10, 8),
    ):
        notify_parents_session_rescheduled(FakeDb(), old, new, case_id=3)

    assert templates == ["session_rescheduled_today"]


PARENT_TEMPLATES = [
    "session_log_submitted",
    "report_published",
    "invoice_generated",
    "payment_reminder",
    "session_cancelled_today",
    "session_rescheduled_today",
    "incident_family_notice",
    "parent_support_escalated",
    "support_ticket_reply",
    "incident_staff_reply",
    "child_absence_confirmed",
    "leave_sessions_cancelled",
    "cm_meeting_cancelled",
    "cm_meeting_invite",
]

LOGIN_TEMPLATES = ["portal_invite", "password_reset"]


@pytest.mark.parametrize("template_key", PARENT_TEMPLATES)
def test_parent_templates_include_opt_out_footer(template_key):
    payload = {
        "parent_name": "Test",
        "child_name": "Child",
        "manage_prefs_url": "https://app.example/parent/profile#email-preferences",
        "portal_url": "https://app.example/parent",
        "when": "2026-10-08 10:00",
        "old_when": "2026-10-08 09:00",
        "new_when": "2026-10-08 11:00",
        "reason": "Cancelled",
        "invoice_number": "INV-1",
        "balance_inr": 100,
        "payments_url": "https://app.example/parent/billing",
        "report_label": "Oct 2026",
        "therapist_name": "T",
        "session_date": "2026-10-08",
        "ticket_subject": "Help",
        "incident_date": "2026-10-08",
        "full_name": "Test",
        "meeting_title": "Meet",
    }
    subject, text, html = render_template(template_key, payload)
    assert "Manage your email preferences" in text
    assert "/parent/profile#email-preferences" in text
    assert "Manage your email preferences" in html


@pytest.mark.parametrize("template_key", LOGIN_TEMPLATES)
def test_login_templates_exclude_opt_out_footer(template_key):
    payload = {
        "full_name": "Test",
        "invite_url": "https://app.example/invite",
        "role_label": "Parent",
        "reset_url": "https://app.example/reset",
        "manage_prefs_url": "https://app.example/parent/profile#email-preferences",
    }
    _, text, html = render_template(template_key, payload)
    assert "/parent/profile#email-preferences" not in text
    assert "Manage your email preferences" not in html


def test_cm_meeting_reminder_renders_real_subject():
    subject, _, _ = render_template(
        "cm_meeting_reminder",
        {"full_name": "P", "meeting_title": "Check-in", "when": "Today 3pm"},
    )
    assert subject.startswith("Meeting reminder")
    assert "Notification from Insighte" not in subject


def test_apply_parent_email_preferences_stamps_set_at_on_change():
    user = SimpleNamespace(notification_preferences={}, role_names=["PARENT"])
    apply_parent_email_preferences(user, {"reports": False})
    assert "email_prefs_set_at" in user.notification_preferences
    assert user.notification_preferences["email_reports"] is False
