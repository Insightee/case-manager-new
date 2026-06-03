from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.email_log import EmailLog
from app.models.user import InviteToken, User
from app.services.email.status_helpers import is_submission_success
from app.services.email.suppression_service import get_active_suppression, normalize_email


def latest_login_email_log(db: Session, email: str) -> EmailLog | None:
    email_l = normalize_email(email)
    return db.scalars(
        select(EmailLog)
        .where(
            EmailLog.recipient_email == email_l,
            EmailLog.template_key.in_(("portal_invite", "password_reset")),
        )
        .order_by(EmailLog.created_at.desc())
        .limit(1)
    ).first()


def delivery_metadata_for_email(db: Session, email: str, user: User | None = None) -> dict:
    email_l = normalize_email(email)
    suppression = get_active_suppression(db, email_l)
    log = latest_login_email_log(db, email_l)
    pending = None
    if user:
        now = datetime.now(timezone.utc)
        pending = db.scalars(
            select(InviteToken)
            .where(
                InviteToken.email == email_l,
                InviteToken.used_at.is_(None),
                InviteToken.expires_at > now,
            )
            .order_by(InviteToken.id.desc())
            .limit(1)
        ).first()

    delivery_status = None
    if pending and pending.email_delivery_status:
        delivery_status = pending.email_delivery_status
    elif log:
        delivery_status = log.status
        if delivery_status == "sent":
            delivery_status = "accepted"

    last_sent = None
    if log and (log.sent_at or log.created_at):
        last_sent = (log.sent_at or log.created_at).isoformat()

    return {
        "email_delivery_status": delivery_status or "not_sent",
        "email_attempt_count": (
            pending.email_attempt_count if pending else (log.attempt_count if log else 0)
        ),
        "last_email_status": log.status if log else None,
        "last_email_sent_at": last_sent,
        "next_retry_at": (
            pending.email_next_retry_at.isoformat()
            if pending and pending.email_next_retry_at
            else (log.next_retry_at.isoformat() if log and log.next_retry_at else None)
        ),
        "resend_allowed_at": (
            pending.resend_allowed_at.isoformat() if pending and pending.resend_allowed_at else None
        ),
        "is_email_suppressed": suppression is not None,
        "suppression_reason": suppression.reason if suppression else None,
        "delivery_pending": bool(
            log and is_submission_success(log.status) and log.status != "delivered"
        ),
    }
