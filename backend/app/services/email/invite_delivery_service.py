from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.email_log import EmailLog, EmailLogStatus
from app.models.user import InviteToken


def _now() -> datetime:
    return datetime.now(timezone.utc)


def sync_invite_from_log(db: Session, invite: InviteToken | None, log: EmailLog) -> None:
    if not invite:
        return
    status = log.status
    if status == EmailLogStatus.SENT.value:
        status = EmailLogStatus.ACCEPTED.value
    invite.email_delivery_status = status
    invite.email_attempt_count = log.attempt_count or 0
    if log.last_attempt_at:
        invite.email_last_attempt_at = log.last_attempt_at
    if log.attempt_count == 1 and not invite.email_first_attempt_at:
        invite.email_first_attempt_at = log.last_attempt_at or log.created_at
    invite.email_next_retry_at = log.next_retry_at
    if status == EmailLogStatus.FAILED_FINAL.value:
        invite.delivery_failed_at = _now()
        invite.expired_due_to_delivery_failure = True
        invite.expires_at = _now()
    elif status == EmailLogStatus.HARD_BOUNCED.value:
        invite.delivery_failed_at = _now()
        invite.expired_due_to_delivery_failure = True
        invite.expires_at = _now()
        invite.email_delivery_status = "hard_bounced"
    db.flush()


def set_resend_allowed_at(invite: InviteToken, *, minutes: int | None = None) -> None:
    delay = minutes if minutes is not None else settings.email_template_dedupe_minutes
    invite.resend_allowed_at = _now() + timedelta(minutes=delay)


def expire_invite_delivery_failure(db: Session, invite: InviteToken) -> None:
    now = _now()
    invite.expired_due_to_delivery_failure = True
    invite.delivery_failed_at = now
    invite.expires_at = now
    invite.email_delivery_status = EmailLogStatus.FAILED_FINAL.value
    db.flush()
