from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.email_log import EmailLog, EmailLogStatus


def create_email_log(
    db: Session,
    *,
    event_type: str,
    recipient_email: str,
    subject: str,
    template_key: str,
    payload: dict[str, Any],
    recipient_role: str | None = None,
    provider: str = "smtp",
    entity_type: str | None = None,
    entity_id: int | None = None,
    idempotency_key: str | None = None,
) -> EmailLog:
    row = EmailLog(
        event_type=event_type,
        recipient_email=recipient_email.strip().lower(),
        recipient_role=recipient_role,
        subject=subject,
        template_key=template_key,
        payload_json=payload,
        provider=provider,
        status=EmailLogStatus.QUEUED.value,
        entity_type=entity_type,
        entity_id=entity_id,
        idempotency_key=idempotency_key,
        attempt_count=0,
    )
    db.add(row)
    db.flush()
    return row


def mark_email_accepted(
    db: Session,
    log: EmailLog,
    *,
    provider: str,
    provider_message_id: str | None = None,
) -> None:
    now = datetime.now(timezone.utc)
    log.status = EmailLogStatus.ACCEPTED.value
    log.provider = provider
    log.provider_message_id = provider_message_id
    log.sent_at = now
    log.last_attempt_at = now
    log.error_message = None
    log.updated_at = now


def mark_email_sent(
    db: Session,
    log: EmailLog,
    *,
    provider: str,
    provider_message_id: str | None = None,
) -> None:
    """Legacy noop path — maps to accepted."""
    mark_email_accepted(db, log, provider=provider, provider_message_id=provider_message_id)


def mark_email_failed(db: Session, log: EmailLog, *, error_message: str, provider: str | None = None) -> None:
    log.status = EmailLogStatus.FAILED.value
    log.error_message = error_message[:4000]
    log.last_attempt_at = datetime.now(timezone.utc)
    if provider:
        log.provider = provider


def mark_email_status(
    db: Session,
    log: EmailLog,
    status: str,
    *,
    error_message: str | None = None,
    provider: str | None = None,
    increment_attempt: bool = False,
    schedule_retry_minutes: int | None = None,
) -> None:
    now = datetime.now(timezone.utc)
    log.status = status
    log.updated_at = now
    log.last_attempt_at = now
    if increment_attempt:
        log.attempt_count = (log.attempt_count or 0) + 1
    if error_message is not None:
        log.error_message = error_message[:4000]
    if provider:
        log.provider = provider
    if schedule_retry_minutes is not None:
        log.next_retry_at = now + timedelta(minutes=schedule_retry_minutes)
    elif status not in (
        EmailLogStatus.FAILED_RETRYING.value,
        EmailLogStatus.SOFT_BOUNCED.value,
        EmailLogStatus.PROCESS_FAILED.value,
    ):
        log.next_retry_at = None
