from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.core.database import SessionLocal
from app.models.email_log import EmailLog, EmailLogStatus
from app.services.email.events import EmailEvent
from app.services.email.senders import from_email_for_event
from app.services.email.service import (
    _deliver_email_log,
    enqueue_email_event,
    is_smtp_configured,
)
from app.services.email.templates import render_template


def test_sender_routing_by_event():
    with patch("app.services.email.senders.settings") as mock_settings:
        mock_settings.smtp_from_email = "noreply@insighte.in"
        mock_settings.smtp_from_billing_email = "billing.noreply@insighte.in"
        mock_settings.smtp_from_verification_email = "verification.noreply@insighte.in"
        assert from_email_for_event(EmailEvent.PASSWORD_RESET) == "verification.noreply@insighte.in"
        assert from_email_for_event(EmailEvent.INVOICE_GENERATED) == "billing.noreply@insighte.in"
        assert from_email_for_event(EmailEvent.PORTAL_INVITE) == "noreply@insighte.in"


def test_sender_falls_back_to_primary_when_dedicated_from_unset():
    with patch("app.services.email.senders.settings") as mock_settings:
        mock_settings.smtp_from_email = "noreply@insighte.in"
        mock_settings.smtp_from_billing_email = ""
        mock_settings.smtp_from_verification_email = ""
        assert from_email_for_event(EmailEvent.PASSWORD_RESET) == "noreply@insighte.in"
        assert from_email_for_event(EmailEvent.INVOICE_GENERATED) == "noreply@insighte.in"


def test_render_portal_invite_template():
    subject, text, html = render_template(
        "portal_invite",
        {
            "full_name": "Sam",
            "invite_url": "https://app.example/invite/abc",
            "role_label": "Therapist",
            "intro_line": "You are invited.",
        },
    )
    assert "invited" in subject.lower()
    assert "https://app.example/invite/abc" in text
    assert "Insighte" in html


def test_render_password_reset_template():
    subject, text, html = render_template(
        "password_reset",
        {"full_name": "Alex", "reset_url": "https://app.example/reset/abc", "expires_hours": 1},
    )
    assert "Reset" in subject
    assert "https://app.example/reset/abc" in text
    assert "Insighte" in html
    assert "https://app.example/reset/abc" in html


def test_is_smtp_configured_requires_host_and_from():
    with patch("app.services.email.service.settings") as mock_settings:
        mock_settings.smtp_host = ""
        mock_settings.smtp_from_header = "noreply@example.com"
        assert is_smtp_configured() is False
        mock_settings.smtp_host = "smtp.example.com"
        mock_settings.smtp_from_header = "Test <noreply@example.com>"
        assert is_smtp_configured() is True


def test_deliver_noop_when_smtp_missing():
    db = SessionLocal()
    try:
        from app.services.email import logging as email_logging

        row = email_logging.create_email_log(
            db,
            event_type=EmailEvent.PASSWORD_RESET.value,
            recipient_email="test@example.com",
            subject="Reset",
            template_key="password_reset",
            payload={"full_name": "T", "reset_url": "http://x", "expires_hours": 1},
            provider="noop",
        )
        db.commit()
        log_id = row.id
    finally:
        db.close()

    with patch("app.services.email.service.is_smtp_configured", return_value=False):
        _deliver_email_log(log_id)

    db = SessionLocal()
    try:
        log = db.get(EmailLog, log_id)
        assert log is not None
        assert log.status == EmailLogStatus.SENT.value
        assert log.provider == "noop"
        assert log.sent_at is not None
    finally:
        db.close()


def test_deliver_marks_failed_on_smtp_error():
    db = SessionLocal()
    try:
        from app.services.email import logging as email_logging

        row = email_logging.create_email_log(
            db,
            event_type=EmailEvent.INVOICE_GENERATED.value,
            recipient_email="parent@example.com",
            subject="Invoice",
            template_key="invoice_generated",
            payload={
                "parent_name": "P",
                "invoice_number": "INV-1",
                "child_name": "Child",
                "total_inr": 1000,
                "balance_inr": 500,
                "due_date_str": None,
                "is_overdue": False,
                "payments_url": "http://pay",
            },
        )
        db.commit()
        log_id = row.id
    finally:
        db.close()

    with (
        patch("app.services.email.service.is_smtp_configured", return_value=True),
        patch("app.services.email.service.settings") as mock_settings,
        patch("app.services.email.service._smtp_provider") as mock_provider,
    ):
        mock_settings.smtp_from_header = "Insighte <noreply@insighte.in>"
        mock_provider.name = "smtp"
        mock_provider.send.return_value = MagicMock(ok=False, error="connection refused")
        _deliver_email_log(log_id)

    db = SessionLocal()
    try:
        log = db.get(EmailLog, log_id)
        assert log.status == EmailLogStatus.FAILED.value
        assert "connection refused" in (log.error_message or "")
    finally:
        db.close()


def test_enqueue_creates_queued_log():
    db = SessionLocal()
    bg = MagicMock()
    try:
        with patch("app.services.email.service.is_smtp_configured", return_value=False):
            log_id = enqueue_email_event(
                bg,
                db,
                event=EmailEvent.PASSWORD_RESET,
                to="queued@example.com",
                template_key="password_reset",
                payload={"full_name": "Q", "reset_url": "http://r", "expires_hours": 1},
            )
        db.commit()
        assert log_id is not None
        row = db.get(EmailLog, log_id)
        assert row.status == EmailLogStatus.QUEUED.value
        assert row.recipient_email == "queued@example.com"
        bg.add_task.assert_called_once()
    finally:
        db.close()


def test_enqueue_skips_empty_recipient():
    db = SessionLocal()
    bg = MagicMock()
    try:
        log_id = enqueue_email_event(
            bg,
            db,
            event=EmailEvent.SECURITY_ALERT,
            to="  ",
            template_key="password_reset",
            payload={},
        )
        assert log_id is None
    finally:
        db.close()
