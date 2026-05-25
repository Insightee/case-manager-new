from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.case import Case
from app.models.user import InviteToken, User
from app.services import family_admin_service, parent_service


def ensure_parent_portal_invite_for_case(
    db: Session,
    case_id: int,
    invited_by_user_id: int,
) -> str | None:
    """Send parent portal invite when therapy starts if parent exists but has no active invite."""
    case = db.get(Case, case_id)
    if not case or not case.child_id:
        return None
    parent_user_id = parent_service.primary_parent_user_id_for_child(db, case.child_id)
    if not parent_user_id:
        return None
    user = db.get(User, parent_user_id)
    if not user or not user.email:
        return None
    now = datetime.now(timezone.utc)
    existing = db.scalars(
        select(InviteToken).where(
            InviteToken.email == user.email.lower(),
            InviteToken.used_at.is_(None),
            InviteToken.expires_at > now,
        )
    ).first()
    if existing:
        return None
    try:
        return family_admin_service.issue_parent_invite(
            db, parent_user_id, invited_by_user_id, child_id=case.child_id, send_email=True
        )
    except ValueError:
        return None
