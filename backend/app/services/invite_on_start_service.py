from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.case import Case
from app.models.child import Child
from app.models.user import InviteToken, User
from app.services import appointment_notification_service as appt_notify, family_admin_service, parent_service


def _pending_intake_invite(db: Session, case: Case) -> InviteToken | None:
    if not case.child_id:
        return None
    rows = db.scalars(
        select(InviteToken).where(
            InviteToken.linked_child_id == case.child_id,
            InviteToken.used_at.is_(None),
        )
    ).all()
    now = datetime.now(timezone.utc)
    for inv in rows:
        if inv.expires_at.replace(tzinfo=timezone.utc) <= now:
            continue
        meta = inv.invite_metadata or {}
        if meta.get("pending_case_id") == case.id:
            return inv
    return None


def send_pending_parent_invite(
    db: Session,
    case_id: int,
    therapist_user_id: int,
    *,
    therapist_name: str | None = None,
) -> tuple[bool, str | None]:
    """Send deferred parent portal invite for therapist intake cases. Returns (sent, email)."""
    case = db.get(Case, case_id)
    if not case:
        return False, None
    if parent_service.primary_parent_user_id_for_child(db, case.child_id):
        return False, None
    invite = _pending_intake_invite(db, case)
    if not invite:
        return False, None
    meta = dict(invite.invite_metadata or {})
    if meta.get("invite_sent_at"):
        return False, invite.email
    child = db.get(Child, case.child_id) if case.child_id else None
    child_name = child.full_name if child else meta.get("child_name", "your child")
    client_name = meta.get("client_name") or invite.email
    invite_url = f"{settings.frontend_url}/invite/{invite.token}"
    family_admin_service._send_parent_invite_email(
        invite.email,
        invite_url,
        client_name,
        child_name,
    )
    meta["invite_sent_at"] = datetime.now(timezone.utc).isoformat()
    invite.invite_metadata = meta
    db.flush()
    if therapist_name:
        appt_notify.notify_admins_walk_in_invite(
            db,
            therapist_name=therapist_name,
            client_name=child_name,
            client_email=invite.email,
            slot_when="session started · parent portal invite",
        )
    return True, invite.email


def ensure_parent_portal_invite_for_case(
    db: Session,
    case_id: int,
    invited_by_user_id: int,
    *,
    therapist_name: str | None = None,
) -> tuple[bool, str | None]:
    """On session start: send deferred intake invite or legacy parent-user invite."""
    sent, email = send_pending_parent_invite(
        db, case_id, invited_by_user_id, therapist_name=therapist_name
    )
    if sent:
        return True, email
    case = db.get(Case, case_id)
    if not case or not case.child_id:
        return False, None
    parent_user_id = parent_service.primary_parent_user_id_for_child(db, case.child_id)
    if not parent_user_id:
        return False, None
    user = db.get(User, parent_user_id)
    if not user or not user.email:
        return False, None
    now = datetime.now(timezone.utc)
    existing = db.scalars(
        select(InviteToken).where(
            InviteToken.email == user.email.lower(),
            InviteToken.used_at.is_(None),
            InviteToken.expires_at > now,
        )
    ).first()
    if existing:
        return False, None
    try:
        family_admin_service.issue_parent_invite(
            db, parent_user_id, invited_by_user_id, child_id=case.child_id, send_email=True
        )
        return True, user.email
    except ValueError:
        return False, None
