from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.incident_catalog import (
    category_label,
    route_incident,
    subcategory_label,
    validate_category_subcategory,
)
from app.core.permissions import RoleName
from app.models.case import Case
from app.models.user import User
from app.models.incident import (
    Incident,
    IncidentMessage,
    IncidentPriority,
    IncidentStatus,
    OPEN_INCIDENT_STATUSES,
    normalize_incident_status,
)
from app.services import case_service
from app.services.ticket_escalation_service import find_assignee_for_role


def generate_ticket_code(db: Session) -> str:
    year = datetime.now(timezone.utc).year
    prefix = f"INC-{year}-"
    count = (
        db.scalar(
            select(func.count())
            .select_from(Incident)
            .where(Incident.ticket_code.isnot(None))
            .where(Incident.ticket_code.like(f"{prefix}%"))
        )
        or 0
    )
    return f"{prefix}{count + 1:05d}"


def build_title(
    primary_category: str,
    subcategory: str,
    child_name: str | None,
    case_code: str | None,
) -> str:
    cat = category_label(primary_category)
    sub = subcategory_label(primary_category, subcategory)
    who = child_name or case_code or "Client"
    return f"{cat} · {sub} · {who}"


def resolve_assignee(
    db: Session,
    primary_owner_role: str,
    case: Case | None,
) -> int | None:
    role_map = {
        "CASE_MANAGER": RoleName.CASE_MANAGER.value,
        "HR": RoleName.HR.value,
        "ADMIN": RoleName.ADMIN.value,
    }
    role_name = role_map.get(primary_owner_role, RoleName.CASE_MANAGER.value)
    return find_assignee_for_role(db, role_name, case)


def create_incident(
    db: Session,
    *,
    reporter_user_id: int,
    reporter_role_names: list[str],
    case_id: int | None,
    primary_category: str,
    subcategory: str,
    what_happened: str,
    priority: str | None,
    service_type: str | None,
    incident_at: datetime | None,
    location: str | None,
    immediate_action: str | None,
    child_safe: str | None,
    parent_informed: str | None,
    is_sensitive: bool = False,
) -> Incident:
    validate_category_subcategory(primary_category, subcategory)
    case = case_service.get_case(db, case_id) if case_id else None
    routing = route_incident(
        primary_category,
        subcategory,
        reporter_role_names=reporter_role_names,
    )
    pri = (priority or routing["priority"] or IncidentPriority.NORMAL.value).upper()
    if pri not in {p.value for p in IncidentPriority}:
        pri = IncidentPriority.NORMAL.value

    assignee_id = resolve_assignee(db, routing["primary_owner_role"], case)
    child_name = case_service.case_child_display_name(case) if case else None
    case_code = case.case_code if case else None

    incident = Incident(
        ticket_code=generate_ticket_code(db),
        case_id=case_id,
        reported_by_user_id=reporter_user_id,
        assigned_to_user_id=assignee_id,
        title=build_title(primary_category, subcategory, child_name, case_code),
        description=what_happened.strip(),
        is_sensitive=is_sensitive,
        status=IncidentStatus.REPORTED,
        primary_category=primary_category.strip().upper(),
        subcategory=subcategory.strip().lower(),
        priority=pri,
        service_type=service_type,
        incident_at=incident_at,
        location=location,
        immediate_action=immediate_action,
        child_safe=child_safe,
        parent_informed=parent_informed,
        primary_owner_role=routing["primary_owner_role"],
        tagged_roles=routing.get("tagged_roles") or [],
    )
    db.add(incident)
    db.flush()
    db.add(
        IncidentMessage(
            incident_id=incident.id,
            author_user_id=reporter_user_id,
            body=what_happened.strip(),
        )
    )
    db.flush()
    return incident


def get_incident_detail(db: Session, incident_id: int) -> Incident | None:
    return db.scalars(
        select(Incident)
        .where(Incident.id == incident_id)
        .options(
            selectinload(Incident.messages).selectinload(IncidentMessage.author),
            selectinload(Incident.attachments),
            selectinload(Incident.reporter),
            selectinload(Incident.assignee),
        )
    ).first()


def update_incident(
    db: Session,
    incident: Incident,
    *,
    actor_user_id: int,
    is_owner: bool,
    status: str | None = None,
    priority: str | None = None,
    assigned_to_user_id: int | None = None,
    tagged_roles: list[str] | None = None,
    tagged_user_ids: list[int] | None = None,
    action_taken_note: str | None = None,
) -> Incident:
    if status is not None:
        new_status = normalize_incident_status(status)
        if new_status == IncidentStatus.CLOSED:
            note = (action_taken_note or incident.action_taken_note or "").strip()
            if not note:
                raise ValueError("Action taken note is required before closing")
            incident.action_taken_note = note
        if new_status == IncidentStatus.ACTION_TAKEN and action_taken_note:
            incident.action_taken_note = action_taken_note.strip()
        incident.status = new_status
        if is_owner and new_status in (
            IncidentStatus.IN_REVIEW,
            IncidentStatus.ACTION_TAKEN,
            IncidentStatus.ESCALATED,
            IncidentStatus.CLOSED,
        ):
            incident.last_owner_activity_at = datetime.now(timezone.utc)
        if new_status == IncidentStatus.ESCALATED:
            incident.escalated_at = datetime.now(timezone.utc)

    if priority is not None:
        incident.priority = priority.upper()

    if assigned_to_user_id is not None:
        incident.assigned_to_user_id = assigned_to_user_id

    if tagged_roles is not None:
        incident.tagged_roles = tagged_roles

    if tagged_user_ids is not None:
        incident.tagged_user_ids = [int(x) for x in tagged_user_ids]

    if action_taken_note is not None and not status:
        incident.action_taken_note = action_taken_note.strip()
        if is_owner:
            incident.last_owner_activity_at = datetime.now(timezone.utc)

    db.flush()
    return incident


def mark_in_review_on_owner_open(incident: Incident, actor_user_id: int) -> None:
    if incident.status == IncidentStatus.REPORTED and incident.assigned_to_user_id == actor_user_id:
        incident.status = IncidentStatus.IN_REVIEW
        incident.last_owner_activity_at = datetime.now(timezone.utc)


def _tagged_users_for_detail(db: Session, incident: Incident) -> list[dict]:
    from app.services.incident_notify_service import collect_tagged_user_ids

    ids = collect_tagged_user_ids(db, incident)
    if not ids:
        return []
    users = db.scalars(select(User).where(User.id.in_(ids))).all()
    by_id = {u.id: u for u in users}
    return [
        {"id": uid, "full_name": by_id[uid].full_name, "email": by_id[uid].email}
        for uid in sorted(ids)
        if uid in by_id
    ]


def incident_to_list_dict(incident: Incident, case: Case | None) -> dict:
    status = normalize_incident_status(incident.status).value
    return {
        "id": incident.id,
        "ticket_code": incident.ticket_code,
        "case_id": incident.case_id,
        "case_code": case.case_code if case else None,
        "child_name": case_service.case_child_display_name(case),
        "title": incident.title,
        "status": status,
        "priority": incident.priority,
        "primary_category": incident.primary_category,
        "subcategory": incident.subcategory,
        "is_sensitive": incident.is_sensitive,
        "product_module": case.product_module if case else None,
        "reporter_name": incident.reporter.full_name if incident.reporter else None,
        "assigned_to_user_id": incident.assigned_to_user_id,
        "assigned_to_name": incident.assignee.full_name if incident.assignee else None,
        "primary_owner_role": incident.primary_owner_role,
        "created_at": incident.created_at.isoformat() if incident.created_at else None,
        "incident_at": incident.incident_at.isoformat() if incident.incident_at else None,
    }


def incident_to_detail_dict(
    db: Session,
    incident: Incident,
    case: Case | None,
    user: User | None = None,
) -> dict:
    from app.services import incident_attachment_service as att_svc
    from app.services import incident_flow_service as inc_flow

    base = incident_to_list_dict(incident, case)
    base.update(
        {
            "description": incident.description,
            "service_type": incident.service_type,
            "location": incident.location,
            "immediate_action": incident.immediate_action,
            "child_safe": incident.child_safe,
            "parent_informed": incident.parent_informed,
            "tagged_roles": incident.tagged_roles or [],
            "tagged_user_ids": incident.tagged_user_ids or [],
            "tagged_users": _tagged_users_for_detail(db, incident),
            "action_taken_note": incident.action_taken_note,
            "escalated_at": incident.escalated_at.isoformat() if incident.escalated_at else None,
            "messages": [
                {
                    "id": m.id,
                    "body": m.body,
                    "author_name": m.author.full_name if m.author else "Unknown",
                    "is_reporter": m.author_user_id == incident.reported_by_user_id,
                    "created_at": m.created_at.isoformat(),
                }
                for m in incident.messages
            ],
            "attachments": [att_svc.attachment_to_dict(a) for a in incident.attachments],
        }
    )
    if user is not None:
        base.update(inc_flow.incident_flow_flags(user, incident))
    return base
