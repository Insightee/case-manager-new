from __future__ import annotations

from datetime import datetime, timezone

from fastapi import BackgroundTasks
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.core.timezone import ensure_utc_aware
from app.models.email_log import EmailLog, EmailLogStatus
from app.models.user import InviteToken, User
from app.services.email.delivery_metadata import delivery_metadata_for_email
from app.services.email.service import (
    enqueue_password_reset_email,
    enqueue_portal_invite_email,
    invite_email_delivery_status,
)
from app.services import password_reset_service


def consume_pending_portal_invites(db: Session, user: User, *, reason: str = "activated") -> None:
    """Mark open portal invites consumed; apply invite role when the user has none yet."""
    from app.core.rbac_access import sync_user_access_fields
    from app.models.role import Role

    now = datetime.now(timezone.utc)
    email_l = user.email.lower().strip()
    rows = list(
        db.scalars(
            select(InviteToken)
            .where(
                InviteToken.email == email_l,
                InviteToken.used_at.is_(None),
            )
            .order_by(InviteToken.id.desc())
        ).all()
    )
    if not rows:
        return

    latest = rows[0]
    invite_meta = latest.invite_metadata or {}

    for inv in rows:
        inv.used_at = now
        meta = dict(inv.invite_metadata or {})
        meta["consumed_reason"] = reason
        inv.invite_metadata = meta

    if not (user.role_names or []) and latest.role_name:
        role = db.scalars(select(Role).where(Role.name == latest.role_name)).first()
        if role:
            user.roles = [role]
            sync_user_access_fields(
                user,
                role_names=[latest.role_name],
                module_assignments=latest.module_assignments or [],
                module_access_grants=invite_meta.get("module_access_grants"),
                feature_overrides=invite_meta.get("feature_overrides"),
                view_only=bool(invite_meta.get("view_only", False)),
                db=db,
            )
        if invite_meta.get("department"):
            user.department = invite_meta["department"]

    db.flush()


def login_ready(user: User, db: Session | None = None) -> bool:
    """User can sign in with their chosen password (not a provisional invite-only account)."""
    if not user.is_active or not user.password_hash:
        return False
    if db is not None and _pending_invite(db, user.email) is not None:
        return False
    if db is not None and "PARENT" in (user.role_names or []):
        from app.services.parent_service import parent_has_portal_session

        if not parent_has_portal_session(db, user.id):
            return False
    return True


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
            InviteToken.expired_due_to_delivery_failure.is_(False),
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
    if latest.expired_due_to_delivery_failure:
        return "delivery_failed"
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


def _pending_invites_by_email(db: Session, emails: list[str]) -> dict[str, InviteToken]:
    """Latest unused, non-expired invite per email (batch)."""
    if not emails:
        return {}
    now = datetime.now(timezone.utc)
    normalized = [e.lower().strip() for e in emails if e]
    if not normalized:
        return {}
    rows = list(
        db.scalars(
            select(InviteToken)
            .where(
                InviteToken.email.in_(normalized),
                InviteToken.used_at.is_(None),
                InviteToken.expires_at > now,
                InviteToken.expired_due_to_delivery_failure.is_(False),
            )
            .order_by(InviteToken.email.asc(), InviteToken.id.desc())
        ).all()
    )
    out: dict[str, InviteToken] = {}
    for inv in rows:
        key = inv.email.lower().strip()
        if key not in out:
            out[key] = inv
    return out


def _invite_status_from_rows(rows: list[InviteToken]) -> str:
    if not rows:
        return "none"
    latest = rows[0]
    if latest.used_at is not None:
        return "used"
    if latest.expired_due_to_delivery_failure:
        return "delivery_failed"
    if ensure_utc_aware(latest.expires_at) <= datetime.now(timezone.utc):
        return "expired"
    return "pending"


def _invite_statuses_by_email(db: Session, emails: list[str]) -> dict[str, str]:
    if not emails:
        return {}
    normalized = [e.lower().strip() for e in emails if e]
    if not normalized:
        return {}
    rows = list(
        db.scalars(
            select(InviteToken)
            .where(InviteToken.email.in_(normalized))
            .order_by(InviteToken.email.asc(), InviteToken.id.desc())
        ).all()
    )
    grouped: dict[str, list[InviteToken]] = {}
    for inv in rows:
        key = inv.email.lower().strip()
        bucket = grouped.setdefault(key, [])
        if len(bucket) < 5:
            bucket.append(inv)
    return {email: _invite_status_from_rows(grouped.get(email, [])) for email in normalized}


def _last_login_email_by_email(db: Session, emails: list[str]) -> dict[str, datetime]:
    if not emails:
        return {}
    normalized = [e.lower().strip() for e in emails if e]
    if not normalized:
        return {}
    rows = list(
        db.scalars(
            select(EmailLog)
            .where(
                EmailLog.recipient_email.in_(normalized),
                EmailLog.template_key.in_(("portal_invite", "password_reset")),
            )
            .order_by(EmailLog.recipient_email.asc(), EmailLog.created_at.desc())
        ).all()
    )
    out: dict[str, datetime] = {}
    for row in rows:
        key = row.recipient_email.lower().strip()
        if key not in out:
            sent = row.sent_at or row.created_at
            if sent:
                out[key] = sent
    return out


def _parent_portal_session_user_ids(db: Session, user_ids: list[int]) -> set[int]:
    if not user_ids:
        return set()
    from app.models.audit_event import AuditEvent

    rows = db.scalars(
        select(AuditEvent.actor_user_id)
        .where(
            AuditEvent.actor_user_id.in_(user_ids),
            AuditEvent.action.in_(("login", "accept_invite")),
        )
        .distinct()
    ).all()
    return {int(uid) for uid in rows}


def _login_ready_from_batch(
    user: User,
    *,
    pending_by_email: dict[str, InviteToken],
    portal_session_ids: set[int],
) -> bool:
    if not user.is_active or not user.password_hash:
        return False
    email_key = user.email.lower().strip()
    if pending_by_email.get(email_key) is not None:
        return False
    if "PARENT" in (user.role_names or []) and user.id not in portal_session_ids:
        return False
    return True


def login_metadata_batch(
    db: Session,
    users: list[User],
    *,
    include_delivery: bool = True,
) -> dict[int, dict]:
    """Batch login/invite metadata for a page of users (avoids per-row query storms)."""
    if not users:
        return {}
    emails = [u.email for u in users]
    pending_by_email = _pending_invites_by_email(db, emails)
    invite_status_by_email = _invite_statuses_by_email(db, emails)
    last_email_by_email = _last_login_email_by_email(db, emails)
    parent_ids = [u.id for u in users if "PARENT" in (u.role_names or [])]
    portal_session_ids = _parent_portal_session_user_ids(db, parent_ids)

    delivery_by_email: dict[str, dict] = {}
    if include_delivery:
        for user in users:
            delivery_by_email[user.email.lower().strip()] = delivery_metadata_for_email(
                db, user.email, user
            )

    out: dict[int, dict] = {}
    for user in users:
        email_key = user.email.lower().strip()
        pending = pending_by_email.get(email_key)
        invite_url = (
            f"{settings.frontend_url.rstrip('/')}/invite/{pending.token}" if pending else None
        )
        last_at = last_email_by_email.get(email_key)
        meta = {
            "login_ready": _login_ready_from_batch(
                user,
                pending_by_email=pending_by_email,
                portal_session_ids=portal_session_ids,
            ),
            "invite_status": invite_status_by_email.get(email_key, "none"),
            "last_invite_sent_at": last_at.isoformat() if last_at else None,
            "pending_invite_url": invite_url,
            "primary_role": _primary_role(user),
        }
        if include_delivery:
            meta.update(delivery_by_email.get(email_key, {}))
        out[user.id] = meta
    return out


def login_metadata_for_user(db: Session, user: User) -> dict:
    batch = login_metadata_batch(db, [user], include_delivery=True)
    return batch.get(user.id) or {
        "login_ready": login_ready(user, db),
        "invite_status": invite_status_for_email(db, user.email),
        "last_invite_sent_at": None,
        "pending_invite_url": None,
        "primary_role": _primary_role(user),
        **delivery_metadata_for_email(db, user.email, user),
    }


def _delivery_message(
    *,
    invite_sent: bool,
    invite_error: str | None,
    meta: dict,
) -> str | None:
    if meta.get("is_email_suppressed"):
        return "Email bounced or blocked. Correct the email before resending."
    status = meta.get("email_delivery_status") or ""
    if status == EmailLogStatus.FAILED_FINAL.value or status == "delivery_failed":
        return "Delivery failed after 3 attempts. Verify the email and resend."
    if status == EmailLogStatus.HARD_BOUNCED.value or status == "hard_bounced":
        return "Email hard bounced. Correct the address before resending."
    if meta.get("resend_allowed_at") and not invite_sent:
        return f"Invite already sent. You can resend after {meta['resend_allowed_at']}."
    if meta.get("delivery_pending"):
        return "Invite sent. Delivery pending."
    if invite_error:
        return invite_error
    return None


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
    delivery_message = _delivery_message(
        invite_sent=invite_sent, invite_error=invite_error, meta=meta
    )
    return {
        "email": user.email,
        "role": _primary_role(user),
        "user_created": user_created,
        "user_active": bool(user.is_active),
        "invite_sent": invite_sent,
        "invite_error": invite_error,
        "login_ready": login_ready(user, db),
        "invite_url": invite_url or meta.get("pending_invite_url"),
        "invite_status": meta["invite_status"],
        "last_invite_sent_at": meta["last_invite_sent_at"],
        "email_delivery_status": meta.get("email_delivery_status"),
        "email_attempt_count": meta.get("email_attempt_count"),
        "last_email_status": meta.get("last_email_status"),
        "last_email_sent_at": meta.get("last_email_sent_at"),
        "next_retry_at": meta.get("next_retry_at"),
        "resend_allowed_at": meta.get("resend_allowed_at"),
        "is_email_suppressed": meta.get("is_email_suppressed"),
        "suppression_reason": meta.get("suppression_reason"),
        "delivery_message": delivery_message,
    }


def activate_user_for_login(db: Session, user_id: int) -> dict:
    user = db.get(User, user_id)
    if not user:
        raise ValueError("User not found")
    user.is_active = True
    consume_pending_portal_invites(db, user, reason="activate_for_login")
    db.flush()
    return _build_result(user, db=db, invite_sent=False, invite_error=None)


def _primary_child_id_for_parent(db: Session, user_id: int) -> int | None:
    from app.models.parent import ParentGuardian

    pg = db.scalars(
        select(ParentGuardian)
        .where(ParentGuardian.user_id == user_id)
        .options(selectinload(ParentGuardian.children))
    ).first()
    if not pg or not pg.children:
        return None
    return pg.children[0].id


def invite_user_to_login(
    db: Session,
    user_id: int,
    *,
    actor_user_id: int,
    background_tasks: BackgroundTasks | None,
    send_email: bool = True,
    force_resend: bool = False,
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
    smtp_skipped = delivery == "skipped_no_smtp"

    pending = _pending_invite(db, user.email)
    roles = user.role_names or []
    is_parent = "PARENT" in roles

    try:
        if is_parent and not login_ready(user, db):
            from app.services import family_admin_service

            child_id = _primary_child_id_for_parent(db, user.id)
            invite_url = family_admin_service.refresh_parent_portal_invite(
                db,
                user.id,
                actor_user_id,
                child_id=child_id,
                send_email=not smtp_skipped,
                background_tasks=background_tasks,
                force_resend=force_resend,
            )
            invite_sent = not smtp_skipped and (
                delivery in ("queued", "sent_sync") or background_tasks is not None
            )
            if smtp_skipped:
                invite_error = "smtp_not_configured"
        elif pending:
            invite_url = f"{settings.frontend_url.rstrip('/')}/invite/{pending.token}"
            if background_tasks is not None:
                role = pending.role_name or _primary_role(user) or "USER"
                role_label = role.replace("_", " ").title()
                log_id = enqueue_portal_invite_email(
                    background_tasks,
                    db,
                    to=user.email,
                    invite_url=invite_url,
                    full_name=user.full_name or user.email,
                    role_label=role_label,
                    recipient_role=role.lower(),
                    invite_id=pending.id,
                    force_resend=force_resend,
                )
                invite_sent = log_id is not None or delivery in ("queued", "sent_sync")
                if smtp_skipped:
                    invite_sent = False
                    invite_error = "smtp_not_configured"
                elif log_id is None and not force_resend:
                    invite_error = "cooldown_or_duplicate"
            else:
                invite_sent = False
                invite_error = "background_tasks_required"
        else:
            plain, token_id = password_reset_service.get_or_create_reset_token(
                db, user, force_new=force_resend
            )
            invite_url = f"{settings.frontend_url.rstrip('/')}/reset-password/{plain}"
            if background_tasks is not None:
                log_id = enqueue_password_reset_email(
                    background_tasks,
                    db,
                    to=user.email,
                    full_name=user.full_name or user.email,
                    reset_url=invite_url,
                    expires_hours=settings.password_reset_expire_hours,
                    entity_id=token_id,
                    force_resend=force_resend,
                )
                invite_sent = log_id is not None or delivery == "sent_sync"
                if smtp_skipped:
                    invite_sent = False
                    invite_error = "smtp_not_configured"
                elif log_id is None and not force_resend:
                    invite_error = "cooldown_or_duplicate"
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
