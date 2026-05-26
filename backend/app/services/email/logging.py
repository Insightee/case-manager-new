from __future__ import annotations

from datetime import datetime, timezone
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
    )
    db.add(row)
    db.flush()
    return row


def mark_email_sent(
    db: Session,
    log: EmailLog,
    *,
    provider: str,
    provider_message_id: str | None = None,
) -> None:
    log.status = EmailLogStatus.SENT.value
    log.provider = provider
    log.provider_message_id = provider_message_id
    log.sent_at = datetime.now(timezone.utc)
    log.error_message = None


def mark_email_failed(db: Session, log: EmailLog, *, error_message: str, provider: str | None = None) -> None:
    log.status = EmailLogStatus.FAILED.value
    log.error_message = error_message[:4000]
    if provider:
        log.provider = provider
