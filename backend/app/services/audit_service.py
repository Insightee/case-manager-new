from __future__ import annotations

import json
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.permissions import case_scope_check, user_has_permission
from app.models.audit_event import AuditEvent
from app.models.case import Case
from app.models.user import User

ACTION_LABELS: dict[str, str] = {
    "approve": "Approved",
    "reject": "Rejected",
    "create": "Created",
    "update": "Updated",
    "delete": "Deleted",
    "submit": "Submitted",
    "update_parent_profile": "Updated parent profile",
    "approve_session_log": "Approved session log",
    "reject_session_log": "Rejected session log",
}

TIMELINE_ASSIGNMENT_LIMIT = 20


def humanize_action(action: str) -> str:
    if action in ACTION_LABELS:
        return ACTION_LABELS[action]
    parts = action.replace("_", " ").strip()
    return parts[:1].upper() + parts[1:] if parts else action


def _entity_label(entity_type: str, action: str) -> str:
    et = entity_type.replace("_", " ")
    return f"{humanize_action(action)} {et}"


def _serialize_audit_item(ev: AuditEvent) -> dict[str, Any]:
    actor = ev.actor if ev.actor_user_id else None
    return {
        "id": ev.id,
        "actor_user_id": ev.actor_user_id,
        "actor_name": actor.full_name if actor else "System",
        "actor_email": actor.email if actor else None,
        "action": ev.action,
        "action_label": _entity_label(ev.entity_type, ev.action),
        "entity_type": ev.entity_type,
        "entity_id": ev.entity_id,
        "case_id": ev.case_id,
        "old_value": _parse_json(ev.old_value),
        "new_value": _parse_json(ev.new_value),
        "created_at": ev.created_at.isoformat() if ev.created_at else None,
    }


def list_audit_events(
    db: Session,
    user: User,
    *,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    case_id: Optional[int] = None,
    limit: int = 50,
    cursor: Optional[int] = None,
) -> dict[str, Any]:
    if not (
        user_has_permission(user, "case.read.all")
        or user_has_permission(user, "case.read.team")
        or user_has_permission(user, "admin.override")
    ):
        raise PermissionError("Insufficient permissions")

    stmt = (
        select(AuditEvent)
        .options(joinedload(AuditEvent.actor))
        .order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
    )
    if entity_type:
        stmt = stmt.where(AuditEvent.entity_type == entity_type)
    if entity_id is not None:
        stmt = stmt.where(AuditEvent.entity_id == str(entity_id))
    if cursor:
        stmt = stmt.where(AuditEvent.id < cursor)
    if case_id is not None:
        case = db.get(Case, case_id)
        if not case or not case_scope_check(db, user, case):
            raise PermissionError("Case access denied")
        stmt = stmt.where(AuditEvent.case_id == case_id)

    stmt = stmt.limit(min(limit, 100))
    rows = list(db.scalars(stmt).all())
    items = [_serialize_audit_item(ev) for ev in rows]
    next_cursor = rows[-1].id if rows else None
    return {"items": items, "next_cursor": next_cursor}


def _parse_json(raw: Optional[str]) -> Any:
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def case_timeline(db: Session, user: User, case_id: int, *, limit: int = 40) -> list[dict]:
    case = db.get(Case, case_id)
    if not case or not case_scope_check(db, user, case):
        raise PermissionError("Case access denied")

    from app.models.assignment import CaseAssignment

    events: list[dict] = []

    audit = list_audit_events(db, user, case_id=case_id, limit=limit)
    for item in audit.get("items", []):
        events.append({**item, "source": "audit"})

    assignments = db.scalars(
        select(CaseAssignment)
        .where(CaseAssignment.case_id == case_id)
        .order_by(CaseAssignment.start_date.desc())
        .limit(TIMELINE_ASSIGNMENT_LIMIT)
    ).all()
    therapist_ids = {a.therapist_user_id for a in assignments}
    therapists: dict[int, User] = {}
    if therapist_ids:
        for u in db.scalars(select(User).where(User.id.in_(therapist_ids))).all():
            therapists[u.id] = u
    for a in assignments:
        therapist = therapists.get(a.therapist_user_id)
        events.append(
            {
                "source": "assignment",
                "id": f"assignment-{a.id}",
                "action_label": f"Therapist assigned: {therapist.full_name if therapist else a.therapist_user_id}",
                "created_at": a.start_date.isoformat() if a.start_date else None,
                "entity_type": "case_assignment",
                "entity_id": str(a.id),
            }
        )

    events.sort(key=lambda e: e.get("created_at") or "", reverse=True)
    return events[:limit]
