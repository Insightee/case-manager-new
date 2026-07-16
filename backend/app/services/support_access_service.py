"""Single source of truth for admin support hub visibility and data scope."""
from __future__ import annotations

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.module_access import case_product_module_allowed, user_has_feature
from app.core.permissions import RoleName, case_scope_check, user_has_permission
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


def has_org_wide_support_scope(user: User) -> bool:
    return user_has_permission(user, "admin.override") or user_has_permission(user, "case.read.all")


def is_finance_desk_user(user: User) -> bool:
    """Finance role desk — ticket queues are billing-scoped, not full clinical org queue."""
    roles = set(user.role_names or [])
    if RoleName.FINANCE.value not in roles:
        return False
    if user_has_permission(user, "admin.override"):
        return False
    if RoleName.SUPER_ADMIN.value in roles:
        return False
    return True


def is_hr_desk_user(user: User) -> bool:
    """HR role desk — ticket queues are HR/therapist-chain scoped."""
    roles = set(user.role_names or [])
    if RoleName.HR.value not in roles:
        return False
    if user_has_permission(user, "admin.override"):
        return False
    if RoleName.SUPER_ADMIN.value in roles:
        return False
    return True


def is_admin_desk_user(user: User) -> bool:
    """Operations admin / module admin — general ticket queue only."""
    roles = set(user.role_names or [])
    if user_has_permission(user, "admin.override"):
        return False
    if RoleName.ADMIN.value in roles or RoleName.MODULE_ADMIN.value in roles:
        return can_view_support_tickets(user)
    return False


def is_team_scoped_support_user(user: User) -> bool:
    """Case managers / supervisors — support desk limited to caseload + items routed to them."""
    if has_org_wide_support_scope(user):
        return False
    if not user_has_permission(user, "case.read.team"):
        return False
    return can_view_support_tickets(user) or can_view_support_incidents(user)


def team_support_ticket_clause(user: User):
    from app.models.support_ticket import SupportTicket
    from app.services.admin_scope_service import scoped_case_ids_subquery

    scoped_ids = scoped_case_ids_subquery(user)
    return or_(
        SupportTicket.assigned_to_user_id == user.id,
        SupportTicket.raised_by_user_id == user.id,
        SupportTicket.case_id.in_(scoped_ids),
    )


def team_support_incident_clause(user: User):
    from app.models.incident import Incident
    from app.services.admin_scope_service import scoped_case_ids_subquery

    scoped_ids = scoped_case_ids_subquery(user)
    return or_(
        Incident.assigned_to_user_id == user.id,
        Incident.reported_by_user_id == user.id,
        Incident.case_id.in_(scoped_ids),
    )


def support_scope(user: User, db: Session | None = None) -> str:
    """Queue scope for list/history APIs: org-wide desk, caseload-only, or none."""
    if not (can_view_support_tickets(user, db) or can_view_support_incidents(user, db)):
        return "none"
    if user_has_permission(user, "admin.override"):
        return "full"
    if is_team_scoped_support_user(user):
        return "team"
    if is_finance_desk_user(user) and can_view_support_tickets(user, db):
        return "finance_desk"
    if is_hr_desk_user(user) and can_view_support_tickets(user, db):
        return "hr_desk"
    if is_admin_desk_user(user):
        return "admin_desk"
    return "none"


def may_read_support_ticket(db: Session, user: User, ticket) -> bool:
    """Whether a staff user may view a support ticket in list/detail/history."""
    from app.services import case_service, ticket_escalation_service as ticket_esc
    from app.services.admin_scope_service import team_case_in_scope

    if user_has_permission(user, "admin.override"):
        return True
    if ticket.raised_by_user_id == user.id:
        return True
    if ticket.assigned_to_user_id == user.id:
        return True
    if not can_view_support_tickets(user, db):
        return False
    if is_finance_desk_user(user):
        return ticket_esc.ticket_visible_to_finance_desk(ticket, user_id=user.id)
    if is_hr_desk_user(user):
        return ticket_esc.ticket_visible_to_hr_desk(ticket)
    if is_admin_desk_user(user):
        return ticket_esc.ticket_visible_to_admin_desk(ticket, user_id=user.id)
    if has_org_wide_support_scope(user):
        if ticket.case_id:
            case = case_service.get_case(db, ticket.case_id)
            return bool(case and case_scope_check(db, user, case))
        if ticket.product_module and not case_product_module_allowed(user, ticket.product_module, db):
            return False
        return True
    if is_team_scoped_support_user(user):
        if ticket.case_id:
            case = case_service.get_case(db, ticket.case_id)
            return bool(case and team_case_in_scope(user, case))
        return False
    return False


def can_read_incident(db: Session, user: User, incident) -> bool:
    """Read access for incident detail, attachments, and support hub listing."""
    from app.services import case_service
    from app.services.admin_scope_service import team_case_in_scope

    if incident.reported_by_user_id == user.id:
        return True
    if incident.assigned_to_user_id == user.id:
        return True
    if not can_view_support_incidents(user, db):
        return False
    if user_has_permission(user, "admin.override"):
        return True
    if has_org_wide_support_scope(user):
        if incident.case_id:
            case = case_service.get_case(db, incident.case_id)
            return case is None or case_scope_check(db, user, case)
        return True
    if is_team_scoped_support_user(user):
        if incident.case_id:
            case = case_service.get_case(db, incident.case_id)
            return bool(case and team_case_in_scope(user, case))
        return False
    return False


def can_manage_memos(user: User, db: Session | None = None) -> bool:
    if user_has_permission(user, "admin.override"):
        return True
    return any(
        role in user.role_names
        for role in ("SUPER_ADMIN", "ADMIN", "MODULE_ADMIN", "HR", "FINANCE")
    )


def support_hub_capabilities(user: User, db: Session | None = None) -> dict:
    tickets_tab = can_view_support_tickets(user, db)
    incidents_tab = can_view_support_incidents(user, db)
    memos_tab = can_manage_memos(user, db)
    history_tab = tickets_tab or incidents_tab or memos_tab
    return {
        "scope": support_scope(user, db),
        "tabs": {
            "tickets": tickets_tab,
            "incidents": incidents_tab,
            "memos": memos_tab,
            "history": history_tab,
        },
        "history": {
            "tickets": tickets_tab,
            "incidents": incidents_tab,
        },
        "can_manage_incidents": can_manage_incidents(user, db),
    }
