"""Parent-portal read model for incidents shared with the family."""

from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.incident_catalog import category_label, subcategory_label
from app.core.permissions import RoleName
from app.core.timezone import ensure_utc_aware, IST
from app.models.case import Case
from app.models.child import Child
from app.models.incident import Incident
from app.models.parent import ParentGuardian
from app.models.user import User
from app.services import case_service, parent_service


def _parent_case_ids(db: Session, parent_user_id: int) -> set[int]:
    child_ids = parent_service.child_ids_for_parent(db, parent_user_id)
    if not child_ids:
        return set()
    return set(db.scalars(select(Case.id).where(Case.child_id.in_(child_ids))).all())


def parent_can_view_incident(db: Session, user: User, incident: Incident) -> bool:
    if RoleName.PARENT.value not in user.role_names:
        return False
    if incident.reported_by_user_id == user.id:
        return True
    if not incident.shared_with_family or not incident.case_id:
        return False
    return incident.case_id in _parent_case_ids(db, user.id)


def parent_incidents_query(db: Session, user: User):
    case_ids = _parent_case_ids(db, user.id)
    clauses = [Incident.reported_by_user_id == user.id]
    if case_ids:
        clauses.append(
            (Incident.shared_with_family.is_(True)) & (Incident.case_id.in_(case_ids))
        )
    return select(Incident).where(or_(*clauses)).order_by(Incident.created_at.desc())


def _incident_date_ist(incident: Incident) -> str:
    if not incident.incident_at:
        return ""
    aware = ensure_utc_aware(incident.incident_at)
    if aware is None:
        return ""
    return aware.astimezone(IST).date().isoformat()


def _category_label(incident: Incident) -> str:
    if incident.primary_category:
        primary = category_label(incident.primary_category)
        sub = subcategory_label(incident.primary_category, incident.subcategory or "")
        return f"{primary} — {sub}" if sub else primary
    return incident.title or "Incident"


def incident_to_parent_portal_dict(
    db: Session, incident: Incident, case: Case | None, *, viewer: User
) -> dict:
    """Read-only parent view — no clinical narrative, internal notes, or staff-only fields."""
    from app.services import incident_flow_service as inc_flow

    messages = []
    shared_at = ensure_utc_aware(incident.shared_with_family_at) if incident.shared_with_family_at else None
    for m in incident.messages:
        if getattr(m, "is_internal", False):
            continue
        author_roles = list(m.author.role_names) if m.author else []
        is_parent_author = RoleName.PARENT.value in author_roles
        if is_parent_author and m.author_user_id != viewer.id:
            continue
        if m.author_user_id != viewer.id:
            # Staff discussion from before the family was given access stays staff-only.
            created = ensure_utc_aware(m.created_at) if m.created_at else None
            if shared_at is None or created is None or created < shared_at:
                continue
        messages.append(
            {
                "id": m.id,
                "body": m.body,
                "author_user_id": m.author_user_id,
                "author_name": m.author.full_name if m.author else "Care team",
                "is_reporter": m.author_user_id == incident.reported_by_user_id,
                "created_at": m.created_at.isoformat() if m.created_at else None,
                "attachments": [],
            }
        )
    flow = inc_flow.incident_flow_flags(viewer, incident)
    return {
        "id": incident.id,
        "ticket_code": incident.ticket_code,
        "case_id": incident.case_id,
        "case_code": case.case_code if case else None,
        "child_name": case_service.case_child_display_name(case),
        # Staff-written free-text title is not shown to non-reporting parents (may name others).
        "title": _category_label(incident),
        "incident_type_label": _category_label(incident),
        "incident_date_ist": _incident_date_ist(incident),
        "status": incident.status.value if hasattr(incident.status, "value") else str(incident.status),
        "shared_with_family": bool(incident.shared_with_family),
        "priority": incident.priority,
        "created_at": incident.created_at.isoformat() if incident.created_at else None,
        "incident_at": incident.incident_at.isoformat() if incident.incident_at else None,
        "is_reporter": incident.reported_by_user_id == viewer.id,
        "messages": messages,
        "attachments": [],
        **flow,
    }


def incident_to_parent_list_dict(incident: Incident, case: Case | None, *, viewer: User) -> dict:
    """Parent list row. Reporter rows keep the existing shape; shared (non-reporter) rows are trimmed."""
    from app.services import incident_service as inc_svc

    row = inc_svc.incident_to_list_dict(incident, case)
    if incident.reported_by_user_id == viewer.id:
        return row
    row["title"] = _category_label(incident)
    for key in ("is_sensitive", "assigned_to_user_id", "assigned_to_name", "primary_owner_role"):
        row.pop(key, None)
    return row
