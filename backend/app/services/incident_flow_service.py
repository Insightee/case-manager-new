from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.permissions import RoleName, user_has_permission
from app.models.incident import Incident, IncidentMessage, IncidentStatus, OPEN_INCIDENT_STATUSES
from app.models.user import User
from app.services import case_service
from app.services.ticket_escalation_service import find_assignee_for_role

INCIDENT_ESCALATION_ROLES = [
    RoleName.CASE_MANAGER.value,
    RoleName.HR.value,
    RoleName.ADMIN.value,
    RoleName.SUPER_ADMIN.value,
]


def _role_index(role: str | None) -> int:
    if not role:
        return 0
    try:
        return INCIDENT_ESCALATION_ROLES.index(role)
    except ValueError:
        return 0


def _has_non_reporter_reply(incident: Incident) -> bool:
    for m in incident.messages:
        if m.author_user_id != incident.reported_by_user_id:
            return True
    return False


def _staff_manage(user: User) -> bool:
    from app.core.module_access import user_has_feature

    return user_has_permission(user, "incident.read_sensitive") and user_has_feature(
        user, "incidents"
    )


def incident_flow_flags(user: User, incident: Incident) -> dict:
    is_reporter = incident.reported_by_user_id == user.id
    staff_manage = _staff_manage(user) or user_has_permission(user, "admin.override")
    closed = incident.status == IncidentStatus.CLOSED
    role_idx = _role_index(incident.primary_owner_role)
    max_idx = len(INCIDENT_ESCALATION_ROLES) - 1
    has_staff_reply = _has_non_reporter_reply(incident)

    can_escalate = (
        not closed
        and role_idx < max_idx
        and has_staff_reply
        and incident.status in OPEN_INCIDENT_STATUSES
        and (is_reporter or staff_manage)
    )
    can_close_reporter = (
        is_reporter
        and not closed
        and incident.status in (IncidentStatus.ACTION_TAKEN, IncidentStatus.IN_REVIEW)
    )
    can_close_staff = staff_manage and not closed

    next_role = (
        INCIDENT_ESCALATION_ROLES[role_idx + 1]
        if role_idx < max_idx
        else None
    )

    return {
        "is_reporter": is_reporter,
        "can_escalate": can_escalate,
        "can_close": can_close_reporter or can_close_staff,
        "can_close_reporter": can_close_reporter,
        "can_close_staff": can_close_staff,
        "can_reply": not closed,
        "has_staff_reply": has_staff_reply,
        "escalation_role": incident.primary_owner_role,
        "escalation_next_role": next_role,
    }


def _add_message(db: Session, incident: Incident, author_user_id: int, body: str) -> None:
    db.add(
        IncidentMessage(
            incident_id=incident.id,
            author_user_id=author_user_id,
            body=body,
        )
    )
    db.flush()


def close_incident(
    db: Session,
    user: User,
    incident: Incident,
    *,
    note: str,
) -> None:
    note = (note or "").strip()
    if not note:
        raise ValueError("A closing note is required")

    is_reporter = incident.reported_by_user_id == user.id
    staff_manage = _staff_manage(user) or user_has_permission(user, "admin.override")

    if incident.status == IncidentStatus.CLOSED:
        raise ValueError("Incident is already closed")

    if is_reporter:
        if incident.status not in (
            IncidentStatus.ACTION_TAKEN,
            IncidentStatus.IN_REVIEW,
            IncidentStatus.ESCALATED,
        ):
            raise ValueError("Incident is not ready to close — wait for the team response or escalate")
        incident.action_taken_note = note
        incident.status = IncidentStatus.CLOSED
        _add_message(db, incident, user.id, f"[Closed] Reporter closed: {note}")
        return

    if staff_manage:
        incident.action_taken_note = note
        incident.status = IncidentStatus.CLOSED
        incident.last_owner_activity_at = datetime.now(timezone.utc)
        _add_message(db, incident, user.id, f"[Closed] {note}")
        return

    raise ValueError("Not allowed to close this incident")


def escalate_incident(
    db: Session,
    user: User,
    incident: Incident,
    *,
    reason: str | None = None,
) -> None:
    flags = incident_flow_flags(user, incident)
    if not flags["can_escalate"]:
        raise ValueError("Cannot escalate — wait for a team response first, or incident is already at max level")

    role_idx = _role_index(incident.primary_owner_role)
    next_role = INCIDENT_ESCALATION_ROLES[role_idx + 1]
    case = case_service.get_case(db, incident.case_id) if incident.case_id else None
    assignee = find_assignee_for_role(db, next_role, case)
    if assignee:
        incident.assigned_to_user_id = assignee
    incident.primary_owner_role = next_role
    incident.status = IncidentStatus.ESCALATED
    incident.escalated_at = datetime.now(timezone.utc)
    extra = f" Reason: {reason.strip()}" if reason and reason.strip() else ""
    _add_message(
        db,
        incident,
        user.id,
        f"[Escalated] Escalated to {next_role.replace('_', ' ')}.{extra}",
    )
