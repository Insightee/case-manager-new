"""Single source of truth for admin support hub visibility and data scope."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.module_access import user_has_feature
from app.core.permissions import user_has_permission
from app.models.user import User


def can_view_support_tickets(user: User, db: Session | None = None) -> bool:
    return user_has_permission(user, "admin.override") or user_has_permission(user, "ticket.manage")


def can_view_support_incidents(user: User, db: Session | None = None) -> bool:
    """Listing and history — not gated on the incidents product feature."""
    return (
        user_has_permission(user, "admin.override")
        or user_has_permission(user, "ticket.manage")
        or user_has_permission(user, "incident.read_sensitive")
    )


def can_manage_incidents(user: User, db: Session | None = None) -> bool:
    """Clinical incident workflow (status, assign, escalate)."""
    return user_has_permission(user, "incident.read_sensitive") and user_has_feature(user, "incidents", db)


def support_scope(user: User, db: Session | None = None) -> str:
    """Queue scope for list/history APIs: full org support desk or none."""
    if can_view_support_tickets(user, db) or can_view_support_incidents(user, db):
        return "full"
    return "none"


def can_read_incident(db: Session, user: User, incident) -> bool:
    """Read access for incident detail, attachments, and support hub listing."""
    from app.services import case_service
    from app.core.permissions import case_scope_check

    if incident.reported_by_user_id == user.id:
        return True
    if incident.assigned_to_user_id == user.id:
        return True
    if not can_view_support_incidents(user, db):
        return False
    if user_has_permission(user, "admin.override"):
        return True
    if user_has_permission(user, "ticket.manage") and user_has_permission(user, "case.read.all"):
        return True
    if incident.case_id:
        case = case_service.get_case(db, incident.case_id)
        return case is None or case_scope_check(db, user, case)
    return True


def support_hub_capabilities(user: User, db: Session | None = None) -> dict:
    tickets_tab = can_view_support_tickets(user, db)
    incidents_tab = can_view_support_incidents(user, db)
    history_tab = tickets_tab or incidents_tab
    return {
        "scope": support_scope(user, db),
        "tabs": {
            "tickets": tickets_tab,
            "incidents": incidents_tab,
            "history": history_tab,
        },
        "history": {
            "tickets": tickets_tab,
            "incidents": incidents_tab,
        },
        "can_manage_incidents": can_manage_incidents(user, db),
    }
