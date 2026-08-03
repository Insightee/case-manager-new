"""HR / payroll therapist (employee) identifiers on users.external_employee_id."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import InviteToken, User


def normalize_external_employee_id(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def find_pending_invite_with_external_employee_id(
    db: Session,
    external_id: str | None,
    *,
    exclude_invite_id: int | None = None,
) -> InviteToken | None:
    """Return an unused, unexpired invite that already reserves this Therapist ID."""
    normalized = normalize_external_employee_id(external_id)
    if not normalized:
        return None
    now = datetime.now(timezone.utc)
    invites = db.scalars(
        select(InviteToken).where(
            InviteToken.used_at.is_(None),
            InviteToken.expires_at > now,
        )
    ).all()
    for invite in invites:
        if exclude_invite_id is not None and invite.id == exclude_invite_id:
            continue
        meta = invite.invite_metadata or {}
        reserved = normalize_external_employee_id(meta.get("external_employee_id"))
        if reserved == normalized:
            return invite
    return None


def assert_external_employee_id_available(
    db: Session,
    external_id: str | None,
    *,
    exclude_user_id: int | None = None,
    exclude_invite_id: int | None = None,
) -> None:
    normalized = normalize_external_employee_id(external_id)
    if not normalized:
        return
    stmt = select(User.id).where(User.external_employee_id == normalized)
    if exclude_user_id is not None:
        stmt = stmt.where(User.id != exclude_user_id)
    if db.scalar(stmt):
        raise ValueError(f"Therapist ID '{normalized}' is already assigned to another user")
    pending = find_pending_invite_with_external_employee_id(
        db,
        normalized,
        exclude_invite_id=exclude_invite_id,
    )
    if pending:
        raise ValueError(
            f"Therapist ID '{normalized}' is already reserved on a pending invite for "
            f"{pending.email}. Revoke that invite or choose a different ID."
        )


def apply_external_employee_id(user: User, external_id: str | None) -> None:
    user.external_employee_id = normalize_external_employee_id(external_id)
