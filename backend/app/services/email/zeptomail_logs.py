from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.email_log import EmailLog, EmailLogStatus
from app.models.user import InviteToken
from app.services.email import logging as email_logging
from app.services.email.invite_delivery_service import expire_invite_delivery_failure, sync_invite_from_log
from app.services.email.safe_send import is_login_template
from app.services.email.status_helpers import is_submission_success
from app.services.email.suppression_service import suppress_email

logger = logging.getLogger(__name__)

ZEPTO_API = "https://api.zeptomail.com/v1.1/email"

_STATUS_MAP = {
    "delivered": EmailLogStatus.DELIVERED.value,
    "hard bounce": EmailLogStatus.HARD_BOUNCED.value,
    "hard_bounce": EmailLogStatus.HARD_BOUNCED.value,
    "soft bounce": EmailLogStatus.SOFT_BOUNCED.value,
    "soft_bounce": EmailLogStatus.SOFT_BOUNCED.value,
    "process failed": EmailLogStatus.PROCESS_FAILED.value,
    "process_failed": EmailLogStatus.PROCESS_FAILED.value,
    "queued": EmailLogStatus.PENDING.value,
    "processed": EmailLogStatus.ACCEPTED.value,
    "sent": EmailLogStatus.ACCEPTED.value,
}


def _api_key() -> str:
    return (settings.zeptomail_api_key or settings.zeptomail_mailagent_key or settings.smtp_password or "").strip()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _map_status(raw: str | None) -> str | None:
    if not raw:
        return None
    key = raw.strip().lower()
    return _STATUS_MAP.get(key, key.replace(" ", "_"))


def _fetch_logs(*, client_reference: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    key = _api_key()
    if not key:
        logger.warning("ZeptoMail API key not configured")
        return []
    headers = {"Authorization": f"Zoho-enczapikey {key}", "Accept": "application/json"}
    params: dict[str, Any] = {"limit": limit}
    if client_reference:
        params["client_reference"] = client_reference
    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.get(ZEPTO_API, headers=headers, params=params)
            resp.raise_for_status()
            data = resp.json()
    except Exception:
        logger.exception("ZeptoMail log fetch failed")
        return []
    items = data.get("data") or data.get("emails") or data.get("items") or []
    if isinstance(items, dict):
        items = items.get("email", []) or items.get("emails", [])
    return list(items) if isinstance(items, list) else []


def _apply_terminal_status(db: Session, log: EmailLog, mapped: str, detail: str | None = None) -> None:
    invite = None
    if log.entity_type == "invite_token" and log.entity_id:
        invite = db.get(InviteToken, log.entity_id)

    if mapped == EmailLogStatus.DELIVERED.value:
        email_logging.mark_email_status(db, log, mapped, provider="zeptomail")
        if invite:
            sync_invite_from_log(db, invite, log)
        return

    if mapped == EmailLogStatus.HARD_BOUNCED.value:
        email_logging.mark_email_status(
            db,
            log,
            mapped,
            error_message=detail,
            provider="zeptomail",
        )
        suppress_email(db, log.recipient_email, reason="hard_bounce", source="zeptomail_sync", notes=detail)
        if invite:
            expire_invite_delivery_failure(db, invite)
            invite.email_delivery_status = "hard_bounced"
        return

    retry_delay = settings.email_invite_retry_delay_minutes
    max_attempts = settings.email_invite_max_attempts_24h
    if mapped in (EmailLogStatus.SOFT_BOUNCED.value, EmailLogStatus.PROCESS_FAILED.value):
        if is_login_template(log.template_key) and (log.attempt_count or 0) < max_attempts:
            email_logging.mark_email_status(
                db,
                log,
                mapped,
                error_message=detail,
                provider="zeptomail",
                schedule_retry_minutes=retry_delay,
            )
        else:
            email_logging.mark_email_status(
                db,
                log,
                EmailLogStatus.FAILED_FINAL.value,
                error_message=detail,
                provider="zeptomail",
            )
            if invite:
                expire_invite_delivery_failure(db, invite)
        if invite:
            sync_invite_from_log(db, invite, log)
        return

    email_logging.mark_email_status(db, log, mapped, error_message=detail, provider="zeptomail")
    if invite:
        sync_invite_from_log(db, invite, log)


def _sync_one_log(db: Session, log: EmailLog) -> bool:
    ref = f"email_log:{log.id}"
    items = _fetch_logs(client_reference=ref, limit=5)
    if not items:
        return False
    item = items[0]
    raw_status = item.get("event_name") or item.get("status") or item.get("delivery_status")
    mapped = _map_status(str(raw_status) if raw_status else None)
    if not mapped or mapped == log.status:
        return False
    detail = item.get("reason") or item.get("bounce_reason") or item.get("message")
    _apply_terminal_status(db, log, mapped, str(detail)[:500] if detail else None)
    req_id = item.get("request_id") or item.get("mailagent_message_id")
    if req_id:
        log.provider_request_id = str(req_id)[:255]
    return True


def sync_zeptomail_logs(db: Session, *, limit: int = 50) -> dict[str, int]:
    """Poll ZeptoMail for recent login emails awaiting delivery confirmation."""
    if not settings.zeptomail_log_sync_enabled:
        return {"skipped": 1}

    lookback = _now() - timedelta(hours=settings.zeptomail_log_sync_lookback_hours)
    min_age = _now() - timedelta(minutes=15)
    rows = db.scalars(
        select(EmailLog)
        .where(
            EmailLog.template_key.in_(("portal_invite", "password_reset")),
            EmailLog.created_at >= lookback,
            EmailLog.created_at <= min_age,
            EmailLog.status.in_(
                (
                    EmailLogStatus.ACCEPTED.value,
                    EmailLogStatus.SENT.value,
                    EmailLogStatus.PENDING.value,
                    EmailLogStatus.QUEUED.value,
                )
            ),
        )
        .order_by(EmailLog.id.desc())
        .limit(limit)
    ).all()

    stats = {"checked": 0, "updated": 0}
    for log in rows:
        if is_submission_success(log.status) and log.status == EmailLogStatus.DELIVERED.value:
            continue
        stats["checked"] += 1
        if _sync_one_log(db, log):
            stats["updated"] += 1
    return stats
