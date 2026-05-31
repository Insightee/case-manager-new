"""Rules for creating portal invites — cap duplicates and enforce one email per role type."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import InviteToken, User

MAX_PENDING_INVITES = 1


def _normalize_email(email: str) -> str:
    return email.lower().strip()


def _role_label(role_name: str) -> str:
    return role_name.replace("_", " ").title()


def active_pending_invites(db: Session, email: str) -> list[InviteToken]:
    now = datetime.now(timezone.utc)
    email_l = _normalize_email(email)
    return list(
        db.scalars(
            select(InviteToken)
            .where(
                InviteToken.email == email_l,
                InviteToken.used_at.is_(None),
                InviteToken.expires_at > now,
            )
            .order_by(InviteToken.id.desc())
        ).all()
    )


def assert_can_create_invite(db: Session, email: str, role_name: str) -> None:
    """Raise ValueError when a new invite must not be created."""
    email_l = _normalize_email(email)
    role = (role_name or "").strip().upper()
    if not role:
        raise ValueError("Role is required for invite")

    existing_user = db.scalars(select(User).where(User.email == email_l)).first()
    if existing_user:
        user_roles = {r.upper() for r in (existing_user.role_names or [])}
        if role not in user_roles:
            primary = _role_label(sorted(user_roles)[0]) if user_roles else "another role"
            raise ValueError(
                f"User already present as {primary}. Use Invite to login instead of a new invite."
            )
        # Same role — caller may resend via invite-to-login; block duplicate token storm below

    pending = active_pending_invites(db, email_l)
    role_pending = [inv for inv in pending if (inv.role_name or "").strip().upper() == role]
    if len(role_pending) >= MAX_PENDING_INVITES:
        raise ValueError(
            "Maximum invites sent. Cancel the existing invite before sending a new one."
        )

    for inv in pending:
        inv_role = (inv.role_name or "").strip().upper()
        if inv_role and inv_role != role:
            raise ValueError(
                f"Pending invite exists for {_role_label(inv_role)}. Cancel it before inviting as {_role_label(role)}."
            )


def pending_invite_count(db: Session, email: str) -> int:
    return len(active_pending_invites(db, email))
