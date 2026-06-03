from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi import BackgroundTasks

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.email_log import EmailLog, EmailLogStatus
from app.models.email_suppression import EmailSuppression
from app.models.user import InviteToken, User
from app.services.email.events import EmailEvent
from app.services.email.safe_send import (
    deliver_email_log_smtp,
    prepare_login_email_log,
)
from app.services.email.service import enqueue_email_event
from app.services.email.suppression_service import suppress_email
from app.services.invite_policy_service import MAX_PENDING_INVITES


def _bg() -> BackgroundTasks:
    bg = BackgroundTasks()
    return bg


def test_max_pending_invites_is_one():
    assert MAX_PENDING_INVITES == 1


def test_prepare_skips_suppressed_recipient():
    db = SessionLocal()
    try:
        suppress_email(db, "blocked@example.com", reason="hard_bounce", source="test")
        db.commit()
        prep = prepare_login_email_log(
            db,
            event=EmailEvent.PORTAL_INVITE,
            recipient_email="blocked@example.com",
            template_key="portal_invite",
            payload={"full_name": "X", "invite_url": "http://x", "role_label": "Therapist"},
            subject=None,
            recipient_role="therapist",
            entity_type=None,
            entity_id=None,
        )
        assert prep.skipped is True
        assert prep.status == EmailLogStatus.SKIPPED_SUPPRESSED.value
    finally:
        db.close()


def test_smtp_success_marks_accepted_not_delivered():
    db = SessionLocal()
    try:
        from app.services.email import logging as email_logging

        row = email_logging.create_email_log(
            db,
            event_type=EmailEvent.PORTAL_INVITE.value,
            recipient_email="ok@example.com",
            subject="Invite",
            template_key="portal_invite",
            payload={
                "full_name": "Sam",
                "invite_url": "https://app/invite/x",
                "role_label": "Therapist",
            },
        )
        row.attempt_count = 1
        db.commit()
        log_id = row.id
    finally:
        db.close()

    mock_result = MagicMock(ok=True, provider_message_id="msg-1", error=None)
    with (
        patch("app.services.email.service.is_smtp_configured", return_value=True),
        patch("app.services.email.safe_send.settings") as mock_settings,
        patch("app.services.email.safe_send._smtp_provider") as mock_provider,
    ):
        mock_settings.smtp_from_header = "Insighte <noreply@insighte.in>"
        mock_provider.name = "smtp"
        mock_provider.send.return_value = mock_result
        db = SessionLocal()
        try:
            log = db.get(EmailLog, log_id)
            result = deliver_email_log_smtp(db, log)
            db.commit()
            assert result.status == EmailLogStatus.ACCEPTED.value
            assert log.status == EmailLogStatus.ACCEPTED.value
            assert log.status != EmailLogStatus.DELIVERED.value
        finally:
            db.close()


def test_hard_bounce_suppresses_and_expires_invite():
    db = SessionLocal()
    try:
        invite = InviteToken(
            email="bad@example.com",
            role_name="THERAPIST",
            module_assignments=[],
            token="tok123",
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )
        db.add(invite)
        db.flush()
        from app.services.email import logging as email_logging

        row = email_logging.create_email_log(
            db,
            event_type=EmailEvent.PORTAL_INVITE.value,
            recipient_email="bad@example.com",
            subject="Invite",
            template_key="portal_invite",
            payload={"full_name": "Sam", "invite_url": "https://app/i", "role_label": "Therapist"},
            entity_type="invite_token",
            entity_id=invite.id,
        )
        row.attempt_count = 1
        db.commit()
        log_id = row.id
        invite_id = invite.id
    finally:
        db.close()

    mock_result = MagicMock(ok=False, error="Recipient rejected: bad@example.com", provider_message_id=None)
    with (
        patch("app.services.email.service.is_smtp_configured", return_value=True),
        patch("app.services.email.safe_send.settings") as mock_settings,
        patch("app.services.email.safe_send._smtp_provider") as mock_provider,
    ):
        mock_settings.smtp_from_header = "Insighte <noreply@insighte.in>"
        mock_provider.name = "smtp"
        mock_provider.send.return_value = mock_result
        db = SessionLocal()
        try:
            log = db.get(EmailLog, log_id)
            deliver_email_log_smtp(db, log)
            db.commit()
        finally:
            db.close()

    db = SessionLocal()
    try:
        inv = db.get(InviteToken, invite_id)
        assert inv.expired_due_to_delivery_failure is True
        sup = db.scalars(
            select(EmailSuppression).where(EmailSuppression.email == "bad@example.com")
        ).first()
        assert sup is not None
        assert sup.cleared_at is None
    finally:
        db.close()


def test_transient_failure_keeps_invite_valid():
    db = SessionLocal()
    try:
        invite = InviteToken(
            email="retry@example.com",
            role_name="THERAPIST",
            module_assignments=[],
            token="tok456",
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )
        db.add(invite)
        db.flush()
        from app.services.email import logging as email_logging

        row = email_logging.create_email_log(
            db,
            event_type=EmailEvent.PORTAL_INVITE.value,
            recipient_email="retry@example.com",
            subject="Invite",
            template_key="portal_invite",
            payload={"full_name": "Sam", "invite_url": "https://app/i", "role_label": "Therapist"},
            entity_type="invite_token",
            entity_id=invite.id,
        )
        row.attempt_count = 1
        db.commit()
        log_id = row.id
        invite_id = invite.id
        expires = invite.expires_at
    finally:
        db.close()

    mock_result = MagicMock(ok=False, error="connection timeout", provider_message_id=None)
    with (
        patch("app.services.email.service.is_smtp_configured", return_value=True),
        patch("app.services.email.safe_send.settings") as mock_settings,
        patch("app.services.email.safe_send._smtp_provider") as mock_provider,
    ):
        mock_settings.smtp_from_header = "Insighte <noreply@insighte.in>"
        mock_settings.email_invite_max_attempts_24h = 3
        mock_settings.email_invite_retry_delay_minutes = 15
        mock_provider.name = "smtp"
        mock_provider.send.return_value = mock_result
        db = SessionLocal()
        try:
            log = db.get(EmailLog, log_id)
            deliver_email_log_smtp(db, log)
            db.commit()
        finally:
            db.close()

    db = SessionLocal()
    try:
        inv = db.get(InviteToken, invite_id)
        assert inv.expired_due_to_delivery_failure is False
        assert inv.expires_at == expires
        log = db.get(EmailLog, log_id)
        assert log.status == EmailLogStatus.FAILED_RETRYING.value
        assert log.next_retry_at is not None
    finally:
        db.close()


def test_enqueue_dedupe_within_cooldown():
    db = SessionLocal()
    bg = MagicMock()
    try:
        with patch("app.services.email.service.is_smtp_configured", return_value=False):
            first = enqueue_email_event(
                bg,
                db,
                event=EmailEvent.PASSWORD_RESET,
                to="dup@example.com",
                template_key="password_reset",
                payload={"full_name": "A", "reset_url": "http://r", "expires_hours": 1},
                entity_type="password_reset_token",
                entity_id=1,
            )
            db.flush()
            second = enqueue_email_event(
                bg,
                db,
                event=EmailEvent.PASSWORD_RESET,
                to="dup@example.com",
                template_key="password_reset",
                payload={"full_name": "A", "reset_url": "http://r", "expires_hours": 1},
                entity_type="password_reset_token",
                entity_id=1,
            )
        assert first is not None
        assert second is None or second == first
    finally:
        db.close()


def test_retry_job_redis_lock():
    from app.core.security import get_redis

    r = get_redis()
    if not r:
        pytest.skip("Redis not available")
    r.delete("email_jobs:lock")
    assert r.set("email_jobs:lock", "1", nx=True, ex=540)
    assert not r.set("email_jobs:lock", "1", nx=True, ex=540)
    r.delete("email_jobs:lock")
