from __future__ import annotations

import logging
import smtplib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from email_validator import EmailNotValidError, validate_email
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.email_log import EmailLog, EmailLogStatus, LOGIN_TEMPLATE_KEYS
from app.models.user import InviteToken
from app.services.email import logging as email_logging
from app.services.email.events import EmailEvent
from app.services.email.invite_delivery_service import (
    expire_invite_delivery_failure,
    set_resend_allowed_at,
    sync_invite_from_log,
)
from app.services.email.providers.smtp import SmtpEmailProvider, parse_envelope_from
from app.services.email.senders import from_header_for_event
from app.services.email.suppression_service import get_active_suppression, normalize_email, suppress_email
from app.services.email.templates import render_template

logger = logging.getLogger(__name__)

_smtp_provider = SmtpEmailProvider()


@dataclass
class SafeSendResult:
    ok: bool
    skipped: bool
    status: str
    reason: str | None
    email_log_id: int | None
    resend_allowed_at: datetime | None = None
    provider_request_id: str | None = None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def is_login_template(template_key: str) -> bool:
    return template_key in LOGIN_TEMPLATE_KEYS


def validate_recipient(email: str) -> tuple[str | None, str | None]:
    email_l = normalize_email(email)
    if not email_l:
        return None, "empty_email"
    try:
        validated = validate_email(email_l, check_deliverability=False)
        return validated.normalized.lower(), None
    except EmailNotValidError as exc:
        return None, str(exc)[:200]


def _build_idempotency_key(
    recipient: str,
    template_key: str,
    entity_type: str | None,
    entity_id: int | None,
) -> str:
    return f"{recipient}|{template_key}|{entity_type or ''}|{entity_id or ''}"


def _recent_duplicate(
    db: Session,
    *,
    recipient: str,
    template_key: str,
    entity_type: str | None,
    entity_id: int | None,
    within_minutes: int,
) -> EmailLog | None:
    since = _now() - timedelta(minutes=within_minutes)
    q = (
        select(EmailLog)
        .where(
            EmailLog.recipient_email == recipient,
            EmailLog.template_key == template_key,
            EmailLog.created_at >= since,
        )
        .order_by(EmailLog.id.desc())
        .limit(5)
    )
    if entity_type is not None:
        q = q.where(EmailLog.entity_type == entity_type)
    if entity_id is not None:
        q = q.where(EmailLog.entity_id == entity_id)
    rows = list(db.scalars(q).all())
    for row in rows:
        if row.status in (
            EmailLogStatus.SKIPPED_DUPLICATE.value,
            EmailLogStatus.SKIPPED_RATE_LIMITED.value,
            EmailLogStatus.SKIPPED_SUPPRESSED.value,
        ):
            continue
        return row
    return None


def _recipient_daily_count(db: Session, recipient: str) -> int:
    since = _now() - timedelta(hours=24)
    return int(
        db.scalar(
            select(func.count())
            .select_from(EmailLog)
            .where(
                EmailLog.recipient_email == recipient,
                EmailLog.created_at >= since,
                EmailLog.status.notin_(
                    [
                        EmailLogStatus.SKIPPED_DUPLICATE.value,
                        EmailLogStatus.SKIPPED_RATE_LIMITED.value,
                        EmailLogStatus.SKIPPED_SUPPRESSED.value,
                        EmailLogStatus.SKIPPED_INVALID_EMAIL.value,
                    ]
                ),
            )
        )
        or 0
    )


def _invite_attempts_in_24h(
    db: Session,
    *,
    recipient: str,
    template_key: str,
    entity_type: str | None,
    entity_id: int | None,
) -> int:
    since = _now() - timedelta(hours=24)
    q = select(func.coalesce(func.sum(EmailLog.attempt_count), 0)).where(
        EmailLog.recipient_email == recipient,
        EmailLog.template_key == template_key,
        EmailLog.created_at >= since,
    )
    if entity_type:
        q = q.where(EmailLog.entity_type == entity_type)
    if entity_id:
        q = q.where(EmailLog.entity_id == entity_id)
    total = db.scalar(q)
    return int(total or 0)


def _get_invite(db: Session, entity_type: str | None, entity_id: int | None) -> InviteToken | None:
    if entity_type != "invite_token" or not entity_id:
        return None
    return db.get(InviteToken, entity_id)


def prepare_login_email_log(
    db: Session,
    *,
    event: EmailEvent,
    recipient_email: str,
    template_key: str,
    payload: dict[str, Any],
    subject: str | None,
    recipient_role: str | None,
    entity_type: str | None,
    entity_id: int | None,
    force_resend: bool = False,
    is_automatic_retry: bool = False,
    existing_log_id: int | None = None,
) -> SafeSendResult:
    """Pre-send checks for login templates; creates or reuses email_logs row."""
    recipient, invalid_reason = validate_recipient(recipient_email)
    if not recipient:
        return SafeSendResult(
            ok=False,
            skipped=True,
            status=EmailLogStatus.SKIPPED_INVALID_EMAIL.value,
            reason=invalid_reason,
            email_log_id=None,
        )

    suppression = get_active_suppression(db, recipient)
    if suppression:
        invite = _get_invite(db, entity_type, entity_id)
        if invite:
            invite.email_delivery_status = "suppressed"
            db.flush()
        return SafeSendResult(
            ok=False,
            skipped=True,
            status=EmailLogStatus.SKIPPED_SUPPRESSED.value,
            reason=suppression.reason,
            email_log_id=None,
        )

    invite = _get_invite(db, entity_type, entity_id)
    if invite and invite.resend_allowed_at and not force_resend and not is_automatic_retry:
        ra = invite.resend_allowed_at
        if ra.tzinfo is None:
            ra = ra.replace(tzinfo=timezone.utc)
        if ra > _now():
            return SafeSendResult(
                ok=False,
                skipped=True,
                status=EmailLogStatus.SKIPPED_RATE_LIMITED.value,
                reason="cooldown",
                email_log_id=None,
                resend_allowed_at=ra,
            )

    if not force_resend and not is_automatic_retry:
        dup = _recent_duplicate(
            db,
            recipient=recipient,
            template_key=template_key,
            entity_type=entity_type,
            entity_id=entity_id,
            within_minutes=settings.email_template_dedupe_minutes,
        )
        if dup:
            ra = _now() + timedelta(minutes=settings.email_template_dedupe_minutes)
            if invite:
                set_resend_allowed_at(invite)
            return SafeSendResult(
                ok=False,
                skipped=True,
                status=EmailLogStatus.SKIPPED_DUPLICATE.value,
                reason="duplicate",
                email_log_id=dup.id,
                resend_allowed_at=invite.resend_allowed_at if invite else ra,
            )

    max_attempts = settings.email_invite_max_attempts_24h
    if is_automatic_retry and existing_log_id:
        log = db.get(EmailLog, existing_log_id)
        if not log:
            return SafeSendResult(False, True, EmailLogStatus.FAILED_FINAL.value, "log_missing", None)
        if (log.attempt_count or 0) >= max_attempts:
            return SafeSendResult(False, True, EmailLogStatus.FAILED_FINAL.value, "max_attempts", log.id)
    elif not is_automatic_retry:
        prior_attempts = _invite_attempts_in_24h(
            db,
            recipient=recipient,
            template_key=template_key,
            entity_type=entity_type,
            entity_id=entity_id,
        )
        if prior_attempts >= max_attempts and not force_resend:
            if invite:
                expire_invite_delivery_failure(db, invite)
            return SafeSendResult(
                ok=False,
                skipped=True,
                status=EmailLogStatus.FAILED_FINAL.value,
                reason="max_attempts_24h",
                email_log_id=None,
            )

    if _recipient_daily_count(db, recipient) >= settings.email_recipient_max_per_day and not is_automatic_retry:
        return SafeSendResult(
            ok=False,
            skipped=True,
            status=EmailLogStatus.SKIPPED_RATE_LIMITED.value,
            reason="daily_cap",
            email_log_id=None,
        )

    subj, _, _ = render_template(template_key, payload)
    final_subject = subject or subj
    idem = _build_idempotency_key(recipient, template_key, entity_type, entity_id)

    if is_automatic_retry and existing_log_id:
        log = db.get(EmailLog, existing_log_id)
        if not log:
            return SafeSendResult(False, True, EmailLogStatus.FAILED_FINAL.value, "log_missing", None)
        log.attempt_count = (log.attempt_count or 0) + 1
        log.status = EmailLogStatus.QUEUED.value
        log.updated_at = _now()
        db.flush()
    else:
        log = email_logging.create_email_log(
            db,
            event_type=event.value,
            recipient_email=recipient,
            subject=final_subject,
            template_key=template_key,
            payload=payload,
            recipient_role=recipient_role,
            entity_type=entity_type,
            entity_id=entity_id,
            idempotency_key=idem,
        )
        log.attempt_count = 1
        log.last_attempt_at = _now()
        db.flush()

    if invite:
        sync_invite_from_log(db, invite, log)
        if not is_automatic_retry:
            set_resend_allowed_at(invite)
        invite.email_first_attempt_at = invite.email_first_attempt_at or log.last_attempt_at
        db.flush()

    return SafeSendResult(
        ok=True,
        skipped=False,
        status=EmailLogStatus.QUEUED.value,
        reason=None,
        email_log_id=log.id,
        resend_allowed_at=invite.resend_allowed_at if invite else None,
    )


def deliver_email_log_smtp(db: Session, log: EmailLog) -> SafeSendResult:
    """Submit one log row to SMTP with safety post-processing."""
    subject, body_text, body_html = render_template(log.template_key, log.payload_json)
    if log.subject:
        subject = log.subject

    from app.services.email.service import is_smtp_configured

    if not is_smtp_configured():
        email_logging.mark_email_accepted(db, log, provider="noop")
        return SafeSendResult(True, False, EmailLogStatus.ACCEPTED.value, None, log.id)

    try:
        event = EmailEvent(log.event_type)
        from_header = from_header_for_event(event)
    except ValueError:
        from_header = settings.smtp_from_header
    envelope = parse_envelope_from(from_header)
    client_ref = f"email_log:{log.id}"

    result = _smtp_provider.send(
        to=[log.recipient_email],
        subject=subject,
        body_text=body_text,
        body_html=body_html,
        from_header=from_header,
        envelope_from=envelope,
        client_reference=client_ref,
    )

    invite = _get_invite(db, log.entity_type, log.entity_id)
    retry_delay = settings.email_invite_retry_delay_minutes
    max_attempts = settings.email_invite_max_attempts_24h

    if result.ok:
        email_logging.mark_email_accepted(
            db,
            log,
            provider=_smtp_provider.name,
            provider_message_id=result.provider_message_id,
        )
        if invite:
            invite.email_delivery_status = EmailLogStatus.ACCEPTED.value
            db.flush()
        return SafeSendResult(True, False, EmailLogStatus.ACCEPTED.value, None, log.id)

    err = result.error or "SMTP send failed"
    is_recipient_refused = "Recipient rejected" in err or isinstance(
        getattr(result, "exc_type", None), type(None)
    )

    if "Recipient rejected" in err:
        email_logging.mark_email_status(
            db,
            log,
            EmailLogStatus.HARD_BOUNCED.value,
            error_message=err,
            provider=_smtp_provider.name,
        )
        suppress_email(
            db,
            log.recipient_email,
            reason="invalid_recipient",
            source="smtp_error",
            notes=err[:500],
        )
        if invite:
            expire_invite_delivery_failure(db, invite)
            invite.email_delivery_status = "hard_bounced"
        return SafeSendResult(False, False, EmailLogStatus.HARD_BOUNCED.value, err, log.id)

    attempt = log.attempt_count or 1
    if is_login_template(log.template_key) and attempt < max_attempts:
        email_logging.mark_email_status(
            db,
            log,
            EmailLogStatus.FAILED_RETRYING.value,
            error_message=err,
            provider=_smtp_provider.name,
            schedule_retry_minutes=retry_delay,
        )
        if invite:
            invite.email_delivery_status = EmailLogStatus.FAILED_RETRYING.value
            invite.email_next_retry_at = log.next_retry_at
            db.flush()
        return SafeSendResult(False, False, EmailLogStatus.FAILED_RETRYING.value, err, log.id)

    if is_login_template(log.template_key):
        email_logging.mark_email_status(
            db,
            log,
            EmailLogStatus.FAILED_FINAL.value,
            error_message=err,
            provider=_smtp_provider.name,
        )
        if invite:
            expire_invite_delivery_failure(db, invite)
        return SafeSendResult(False, False, EmailLogStatus.FAILED_FINAL.value, err, log.id)

    email_logging.mark_email_failed(db, log, error_message=err, provider=_smtp_provider.name)
    return SafeSendResult(False, False, EmailLogStatus.FAILED.value, err, log.id)


def check_suppression_only(db: Session, recipient_email: str) -> bool:
    """True if send should proceed (not suppressed)."""
    recipient, _ = validate_recipient(recipient_email)
    if not recipient:
        return False
    return get_active_suppression(db, recipient) is None
