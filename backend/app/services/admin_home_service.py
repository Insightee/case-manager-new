from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.module_access import user_has_feature
from app.core.permissions import RoleName
from app.models.user import User
from app.services import admin_workbench_service

# When a user has multiple roles, the first match in this tuple wins.
PRIMARY_ROLE_PRIORITY: tuple[RoleName, ...] = (
    RoleName.SUPER_ADMIN,
    RoleName.MODULE_ADMIN,
    RoleName.FINANCE,
    RoleName.HR,
    RoleName.SUPERVISOR,
    RoleName.CASE_MANAGER,
    RoleName.ADMIN,
)

def resolve_primary_role(user: User) -> str:
    names = set(user.role_names or [])
    for role in PRIMARY_ROLE_PRIORITY:
        if role.value in names:
            return role.value
    return RoleName.ADMIN.value


def _landing_route(role: str, user: User, db: Session) -> str:
    if role == RoleName.FINANCE.value:
        return "/admin/invoices"
    if role == RoleName.HR.value:
        return "/admin/people"
    if role == RoleName.CASE_MANAGER.value:
        return "/admin/cm"
    if role in (RoleName.VIEWER.value, RoleName.SUPERVISOR.value):
        if getattr(user, "is_view_only", False) or role == RoleName.VIEWER.value:
            return "/admin/cm"
        if user_has_feature(user, "session_logs", db):
            return "/admin/workbench"
    return "/admin"


def _dashboard_variant(role: str) -> str:
    if role == RoleName.FINANCE.value:
        return "finance"
    if role == RoleName.CASE_MANAGER.value:
        return "caseload"
    if role in (RoleName.MODULE_ADMIN.value, RoleName.SUPER_ADMIN.value):
        return "module_admin"
    if role == RoleName.ADMIN.value:
        return "legacy_admin"
    return "operations"


def _widget(
    *,
    widget_id: str,
    title: str,
    priority: int,
    section: dict | None,
) -> dict | None:
    if section is None:
        return None
    return {
        "id": widget_id,
        "title": title,
        "priority": priority,
        "section": section,
    }


def build_admin_home(db: Session, user: User) -> dict:
    role = resolve_primary_role(user)
    widgets: list[dict] = []

    logs = admin_workbench_service.widget_section_logs(db, user)
    w = _widget(
        widget_id="logs",
        title="Session logs queue",
        priority=1 if role in ("CASE_MANAGER", "SUPERVISOR", "SUPER_ADMIN", "MODULE_ADMIN", "ADMIN") else 3,
        section=logs,
    )
    if w:
        widgets.append(w)

    reports = admin_workbench_service.widget_section_reports(db, user)
    w = _widget(
        widget_id="reports",
        title="Reports queue",
        priority=2 if role in ("CASE_MANAGER", "SUPERVISOR", "SUPER_ADMIN", "MODULE_ADMIN", "ADMIN") else 3,
        section=reports,
    )
    if w:
        widgets.append(w)

    billing = admin_workbench_service.widget_section_billing(db, user)
    w = _widget(
        widget_id="billing",
        title="Billing",
        priority=1 if role == RoleName.FINANCE.value else 4,
        section=billing,
    )
    if w:
        widgets.append(w)

    tickets = admin_workbench_service.widget_section_tickets(db, user)
    w = _widget(widget_id="tickets", title="Support tickets", priority=3, section=tickets)
    if w:
        widgets.append(w)

    if admin_workbench_service.user_may_see_reschedules_widget(user, db):
        reschedules = admin_workbench_service.widget_section_reschedules(db, user)
        w = _widget(
            widget_id="reschedules",
            title="Pending reschedules",
            priority=2,
            section=reschedules,
        )
        if w:
            widgets.append(w)

    observations = admin_workbench_service.widget_section_observations(db, user)
    w = _widget(
        widget_id="observations",
        title="Observation checklists",
        priority=1 if role in ("CASE_MANAGER", "SUPERVISOR", "SUPER_ADMIN", "MODULE_ADMIN", "ADMIN") else 4,
        section=observations,
    )
    if w:
        widgets.append(w)

    status_requests = admin_workbench_service.widget_section_status_requests(db, user)
    w = _widget(
        widget_id="status_requests",
        title="Status change requests",
        priority=2 if role in ("CASE_MANAGER", "SUPERVISOR", "SUPER_ADMIN", "MODULE_ADMIN", "ADMIN") else 5,
        section=status_requests,
    )
    if w:
        widgets.append(w)

    client_claims = admin_workbench_service.widget_section_client_claims(db, user)
    w = _widget(
        widget_id="client_claims",
        title="Client payment claims",
        priority=1 if role == RoleName.FINANCE.value else 5,
        section=client_claims,
    )
    if w:
        widgets.append(w)

    widgets.sort(key=lambda item: item.get("priority", 99))

    return {
        "role": role,
        "landing_route": _landing_route(role, user, db),
        "dashboard_variant": _dashboard_variant(role),
        "widgets": widgets,
        "alerts": admin_workbench_service.build_admin_alerts(db, user),
    }
