from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.incident import Incident
from app.services import case_service, notification_service
from app.services.ticket_escalation_service import resolve_users_for_role_tag


def collect_tagged_user_ids(db: Session, incident: Incident) -> set[int]:
    case = case_service.get_case(db, incident.case_id) if incident.case_id else None
    uids: set[int] = set()
    for uid in incident.tagged_user_ids or []:
        if uid is not None:
            uids.add(int(uid))
    for role in incident.tagged_roles or []:
        for uid in resolve_users_for_role_tag(db, str(role), case):
            uids.add(uid)
    return uids


def notify_incident_tagged(
    db: Session,
    incident: Incident,
    actor_user_id: int,
    *,
    notify_user_ids: set[int],
) -> None:
    if not notify_user_ids:
        return
    label = incident.ticket_code or incident.title
    body = f"You were tagged on incident {label}. Open it from Support → Incidents."
    for uid in notify_user_ids:
        if uid == actor_user_id:
            continue
        notification_service.create_notification(
            db,
            user_id=uid,
            title=f"Tagged on {label}",
            body=body,
            entity_type="incident",
            entity_id=incident.id,
        )
