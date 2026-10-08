"""Notify parents when staff explicitly share an incident with the family."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.core.permissions import RoleName
from app.core.timezone import ensure_utc_aware, IST
from app.models.case import Case
from app.models.incident import Incident, IncidentMessage
from app.models.parent import ParentGuardian
from app.models.child import Child
from app.models.user import User
from app.services import notification_service
from app.services.email.parent_mail import send_parent_email

_REPLY_DEDUPE_MINUTES = 10


def _incident_date_ist(incident: Incident) -> str:
    if not incident.incident_at:
        return ""
    aware = ensure_utc_aware(incident.incident_at)
    if aware is None:
        return ""
    return aware.astimezone(IST).date().isoformat()


def _is_parent_only_portal(user: User) -> bool:
    roles = list(user.role_names or [])
    return len(roles) == 1 and roles[0] == RoleName.PARENT.value


def _parent_users_for_case(db: Session, case_id: int) -> list[User]:
    case = db.get(Case, case_id)
    if not case or not case.child_id:
        return []
    rows = db.scalars(
        select(User)
        .join(ParentGuardian, ParentGuardian.user_id == User.id)
        .join(ParentGuardian.children)
        .where(Child.id == case.child_id)
    ).all()
    return list({u.id: u for u in rows}.values())


def notify_parents_incident_shared(db: Session, incident: Incident, *, background_tasks=None) -> int:
    if not incident.shared_with_family or not incident.case_id:
        return 0
    case = db.scalars(
        select(Case).where(Case.id == incident.case_id).options(selectinload(Case.child))
    ).first()
    if not case:
        return 0
    child_name = case.child.full_name if case.child else "your child"
    incident_date = _incident_date_ist(incident)
    portal_url = f"{settings.frontend_url.rstrip('/')}/parent/support"
    title = "Important update from your care team"
    body = (
        f"We shared an update regarding {child_name}. "
        "Your case manager will contact you with next steps. Open Support in your portal for details."
    )
    count = 0
    for parent in _parent_users_for_case(db, case.id):
        if RoleName.PARENT.value not in parent.role_names:
            continue
        notification_service.create_notification(
            db,
            user_id=parent.id,
            title=title,
            body=body,
            entity_type="incident_notice",
            entity_id=incident.id,
        )
        send_parent_email(
            db,
            parent,
            category="incidents",
            template_key="incident_family_notice",
            payload={
                "parent_name": parent.full_name or parent.email,
                "child_name": child_name,
                "incident_date": incident_date,
                "portal_url": portal_url,
            },
            entity_type="incident",
            entity_id=incident.id,
            background_tasks=background_tasks,
        )
        count += 1
    return count


def notify_parents_incident_staff_reply(
    db: Session,
    incident: Incident,
    message: IncidentMessage,
    *,
    staff_user: User,
    background_tasks=None,
) -> int:
    """Email + in-app only when the incident is explicitly shared with the family."""
    if not incident.shared_with_family or not incident.case_id:
        return 0
    if getattr(message, "is_internal", False):
        return 0
    if _is_parent_only_portal(staff_user):
        return 0
    case = db.scalars(
        select(Case).where(Case.id == incident.case_id).options(selectinload(Case.child))
    ).first()
    if not case:
        return 0
    child_name = case.child.full_name if case.child else "your child"
    portal_url = f"{settings.frontend_url.rstrip('/')}/parent/support"
    title = "Update on your incident report"
    body = (
        f"Your care team added an update regarding {child_name}. "
        "Open Support in your portal for details."
    )
    count = 0
    for parent in _parent_users_for_case(db, case.id):
        if RoleName.PARENT.value not in parent.role_names:
            continue
        notification_service.create_notification(
            db,
            user_id=parent.id,
            title=title,
            body=body,
            entity_type="incident_notice",
            entity_id=incident.id,
        )
        send_parent_email(
            db,
            parent,
            category="incidents",
            template_key="incident_staff_reply",
            payload={
                "parent_name": parent.full_name or parent.email,
                "child_name": child_name,
                "portal_url": portal_url,
            },
            entity_type="incident",
            entity_id=incident.id,
            background_tasks=background_tasks,
            dedupe_window_minutes=_REPLY_DEDUPE_MINUTES,
        )
        count += 1
    return count
