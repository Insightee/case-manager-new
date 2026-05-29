from __future__ import annotations

from datetime import datetime, timezone

from fastapi import BackgroundTasks
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.timezone import ensure_utc_aware
from app.models.email_log import EmailLog
from app.models.user import InviteToken, User
from app.services.email.service import (
    enqueue_password_reset_email,
    enqueue_portal_invite_email,
    invite_email_delivery_status,
)
from app.services import password_reset_service


def login_ready(user: User) -> bool:
    return bool(user.is_active and user.password_hash)


def _primary_role(user: User) -> str | None:
    roles = user.role_names or []
    return roles[0] if roles else None


def _pending_invite(db: Session, email: str) -> InviteToken | None:
    now = datetime.now(timezone.utc)
    return db.scalars(
        select(InviteToken)
        .where(
            InviteToken.email == email.lower().strip(),
            InviteToken.used_at.is_(None),
            InviteToken.expires_at > now,
        )
        .order_by(InviteToken.id.desc())
    ).first()


def invite_status_for_email(db: Session, email: str) -> str:
    now = datetime.now(timezone.utc)
    rows = list(
        db.scalars(
            select(InviteToken)
            .where(InviteToken.email == email.lower().strip())
            .order_by(InviteToken.id.desc())
            .limit(5)
        ).all()
    )
    if not rows:
        return "none"
    latest = rows[0]
    if latest.used_at is not None:
        return "used"
    if ensure_utc_aware(latest.expires_at) <= now:
        return "expired"
    return "pending"


def last_login_email_sent_at(db: Session, email: str) -> datetime | None:
    email_l = email.lower().strip()
    row = db.scalars(
        select(EmailLog)
        .where(
            EmailLog.recipient_email == email_l,
            EmailLog.template_key.in_(("portal_invite", "password_reset")),
        )
        .order_by(EmailLog.created_at.desc())
        .limit(1)
    ).first()
    if not row:
        return None
    return row.sent_at or row.created_at


def login_metadata_for_user(db: Session, user: User) -> dict:
    pending = _pending_invite(db, user.email)
    status = invite_status_for_email(db, user.email)
    last_at = last_login_email_sent_at(db, user.email)
    invite_url = None
    if pending:
        invite_url = f"{settings.frontend_url.rstrip('/')}/invite/{pending.token}"
    return {
        "login_ready": login_ready(user),
        "invite_status": status,
        "last_invite_sent_at": last_at.isoformat() if last_at else None,
        "pending_invite_url": invite_url,
        "primary_role": _primary_role(user),
    }


def _build_result(
    user: User,
    *,
    db: Session,
    user_created: bool = True,
    invite_sent: bool = False,
    invite_error: str | None = None,
    invite_url: str | None = None,
) -> dict:
    meta = login_metadata_for_user(db, user)
    if invite_url:
        meta["pending_invite_url"] = invite_url
    return {
        "email": user.email,
        "role": _primary_role(user),
        "user_created": user_created,
        "user_active": bool(user.is_active),
        "invite_sent": invite_sent,
        "invite_error": invite_error,
        "login_ready": login_ready(user),
        "invite_url": invite_url or meta.get("pending_invite_url"),
        "invite_status": meta["invite_status"],
        "last_invite_sent_at": meta["last_invite_sent_at"],
    }


def activate_user_for_login(db: Session, user_id: int) -> dict:
    user = db.get(User, user_id)
    if not user:
        raise ValueError("User not found")
    user.is_active = True
    db.flush()
    return _build_result(user, db=db, invite_sent=False, invite_error=None)


def invite_user_to_login(
    db: Session,
    user_id: int,
    *,
    actor_user_id: int,
    background_tasks: BackgroundTasks | None,
    send_email: bool = True,
) -> dict:
    """Queue login/reset email for an existing user; never blocks on SMTP."""
    user = db.get(User, user_id)
    if not user:
        raise ValueError("User not found")

    invite_sent = False
    invite_error: str | None = None
    invite_url: str | None = None

    if not send_email:
        return _build_result(
            user,
            db=db,
            invite_sent=False,
            invite_error="invite_disabled",
        )

    delivery = invite_email_delivery_status(
        send_email=True, background_tasks=background_tasks
    )
    if delivery == "skipped_no_smtp":
        return _build_result(
            user,
            db=db,
            invite_sent=False,
            invite_error="smtp_not_configured",
        )

    pending = _pending_invite(db, user.email)

    try:
        if pending:
            invite_url = f"{settings.frontend_url.rstrip('/')}/invite/{pending.token}"
            if background_tasks is not None:
                role = pending.role_name or _primary_role(user) or "USER"
                role_label = role.replace("_", " ").title()
                enqueue_portal_invite_email(
                    background_tasks,
                    db,
                    to=user.email,
                    invite_url=invite_url,
                    full_name=user.full_name or user.email,
                    role_label=role_label,
                    recipient_role=role.lower(),
                )
                invite_sent = delivery in ("queued", "sent_sync")
            else:
                invite_sent = False
                invite_error = "background_tasks_required"
        else:
            plain = password_reset_service.create_reset_token(db, user)
            invite_url = f"{settings.frontend_url.rstrip('/')}/reset-password/{plain}"
            if background_tasks is not None:
                log_id = enqueue_password_reset_email(
                    background_tasks,
                    db,
                    to=user.email,
                    full_name=user.full_name or user.email,
                    reset_url=invite_url,
                    expires_hours=settings.password_reset_expire_hours,
                )
                invite_sent = log_id is not None or delivery == "sent_sync"
            else:
                invite_sent = False
                invite_error = "background_tasks_required"
    except Exception as exc:
        invite_error = str(exc)[:500]
        invite_sent = False

    return _build_result(
        user,
        db=db,
        invite_sent=invite_sent,
        invite_error=invite_error,
        invite_url=invite_url,
    )
