from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.permissions import RoleName
from app.models.incident import Incident, IncidentPriority, IncidentStatus, OPEN_INCIDENT_STATUSES
from app.services import notification_service
from app.services.ticket_escalation_service import find_assignee_for_role
from app.services import case_service


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _working_days_since(start: datetime, end: datetime) -> int:
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    days = 0
    cur = start.date()
    end_d = end.date()
    while cur < end_d:
        cur += timedelta(days=1)
        if cur.weekday() < 5:
            days += 1
    return days


def process_open_incidents(db: Session, incidents: list[Incident]) -> None:
    """Apply SLA rules when managers list incidents (v1 — no cron)."""
    now = _now()
    for inc in incidents:
        if inc.status not in OPEN_INCIDENT_STATUSES:
            continue
        if inc.status in (IncidentStatus.ACTION_TAKEN, IncidentStatus.ESCALATED):
            continue
        created = inc.created_at or now
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        age = now - created
        owner_active = inc.last_owner_activity_at is not None

        if inc.priority == IncidentPriority.CRITICAL.value and not owner_active:
            if age >= timedelta(hours=4) and inc.status != IncidentStatus.ESCALATED:
                inc.status = IncidentStatus.ESCALATED
                inc.escalated_at = now
                _notify_escalation(db, inc, "Critical incident — no owner response in 4 hours")

        if not owner_active:
            if age >= timedelta(hours=48) and inc.status != IncidentStatus.ESCALATED:
                inc.status = IncidentStatus.ESCALATED
                inc.escalated_at = now
                _notify_escalation(db, inc, "No owner update in 48 hours — escalated")
            elif age >= timedelta(hours=24) and not inc.sla_reminder_sent_at:
                inc.sla_reminder_sent_at = now
                _notify_reminder(db, inc)

            if _working_days_since(created, now) >= 4 and inc.status == IncidentStatus.REPORTED:
                inc.status = IncidentStatus.ESCALATED
                inc.escalated_at = now
                _notify_escalation(db, inc, "Open more than 4 working days — escalated")

    db.flush()


def _notify_reminder(db: Session, incident: Incident) -> None:
    if incident.assigned_to_user_id:
        notification_service.create_notification(
            db,
            user_id=incident.assigned_to_user_id,
            title=f"Reminder: {incident.ticket_code or incident.title}",
            body="This incident needs your first response.",
            entity_type="incident",
            entity_id=incident.id,
        )


def _notify_escalation(db: Session, incident: Incident, body: str) -> None:
    uids = set()
    if incident.assigned_to_user_id:
        uids.add(incident.assigned_to_user_id)
    case = case_service.get_case(db, incident.case_id) if incident.case_id else None
    for role in incident.tagged_roles or []:
        uid = find_assignee_for_role(db, role if role != "CASE_MANAGER" else RoleName.CASE_MANAGER.value, case)
        if uid:
            uids.add(uid)
    if incident.primary_owner_role == "HR":
        uid = find_assignee_for_role(db, RoleName.HR.value, case)
        if uid:
            uids.add(uid)
    else:
        uid = find_assignee_for_role(db, RoleName.ADMIN.value, case)
        if uid:
            uids.add(uid)
    for uid in uids:
        notification_service.create_notification(
            db,
            user_id=uid,
            title=f"Escalated: {incident.ticket_code or incident.title}",
            body=body,
            entity_type="incident",
            entity_id=incident.id,
        )
