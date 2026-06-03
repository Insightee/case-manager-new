from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.email_log import EmailLog, LOGIN_TEMPLATE_KEYS
from app.models.user import InviteToken
from app.services.email.events import EmailEvent
from app.services.email.invite_delivery_service import expire_invite_delivery_failure
from app.services.email.safe_send import deliver_email_log_smtp, prepare_login_email_log
from app.services.email.service import send_email
from app.services.email.status_helpers import is_retry_eligible, is_submission_success

logger = logging.getLogger(__name__)

_ALERT_PREFIX = "email_failed_final_alert:"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _select_retry_candidates(db: Session, *, limit: int = 50) -> list[EmailLog]:
    now = _now()
    window_start = now - timedelta(hours=24)
    rows = db.scalars(
        select(EmailLog)
        .where(
            EmailLog.template_key.in_(tuple(LOGIN_TEMPLATE_KEYS)),
            EmailLog.next_retry_at.isnot(None),
            EmailLog.next_retry_at <= now,
            EmailLog.created_at >= window_start,
            EmailLog.attempt_count < settings.email_invite_max_attempts_24h,
        )
        .order_by(EmailLog.next_retry_at.asc())
        .limit(limit * 3)
    ).all()
    out: list[EmailLog] = []
    for row in rows:
        if is_submission_success(row.status):
            continue
        if not is_retry_eligible(row.status):
            continue
        if (row.attempt_count or 0) >= settings.email_invite_max_attempts_24h:
            continue
        out.append(row)
        if len(out) >= limit:
            break
    return out


def _alert_failed_final(db: Session, log: EmailLog) -> None:
    if not settings.email_admin_alert_on_failed_final:
        return
    recipients = settings.admin_notification_email_list
    if not recipients:
        return
    from app.core.security import get_redis

    r = get_redis()
    key = f"{_ALERT_PREFIX}{log.recipient_email.lower()}"
    if r:
        if not r.set(key, "1", nx=True, ex=86400):
            return
    subject = f"[Insighte] Invite email failed — {log.recipient_email}"
    body = (
        f"Login email delivery failed after {log.attempt_count} attempt(s).\n\n"
        f"Recipient: {log.recipient_email}\n"
        f"Template: {log.template_key}\n"
        f"Status: {log.status}\n"
        f"Error: {log.error_message or 'unknown'}\n"
    )
    send_email(to=recipients, subject=subject, body_text=body, db=db)


def retry_one_email_log(db: Session, log: EmailLog) -> str:
    """Retry SMTP delivery for one login email log. Returns outcome label."""
    try:
        event = EmailEvent(log.event_type)
    except ValueError:
        event = EmailEvent.PORTAL_INVITE

    prep = prepare_login_email_log(
        db,
        event=event,
        recipient_email=log.recipient_email,
        template_key=log.template_key,
        payload=dict(log.payload_json or {}),
        subject=log.subject,
        recipient_role=log.recipient_role,
        entity_type=log.entity_type,
        entity_id=log.entity_id,
        is_automatic_retry=True,
        existing_log_id=log.id,
    )
    if prep.skipped:
        if prep.status == "failed_final":
            invite = None
            if log.entity_type == "invite_token" and log.entity_id:
                invite = db.get(InviteToken, log.entity_id)
                if invite:
                    expire_invite_delivery_failure(db, invite)
            _alert_failed_final(db, log)
            return "failed_final"
        return prep.status or "skipped"

    refreshed = db.get(EmailLog, log.id)
    if not refreshed:
        return "missing"
    result = deliver_email_log_smtp(db, refreshed)
    if result.status == "failed_final":
        _alert_failed_final(db, refreshed)
    return result.status


def retry_invite_emails(db: Session, *, limit: int = 50) -> dict[str, int]:
    """Cron entry: retry eligible portal_invite / password_reset logs."""
    stats = {"selected": 0, "retried": 0, "failed_final": 0, "skipped": 0}
    candidates = _select_retry_candidates(db, limit=limit)
    stats["selected"] = len(candidates)
    for log in candidates:
        outcome = retry_one_email_log(db, log)
        if outcome in ("accepted", "sent"):
            stats["retried"] += 1
        elif outcome == "failed_final":
            stats["failed_final"] += 1
        else:
            stats["skipped"] += 1
    db.commit()
    return stats
