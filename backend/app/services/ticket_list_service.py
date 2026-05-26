"""Paginated staff ticket listing with SQL scoping."""
from __future__ import annotations

from typing import Optional

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.module_access import case_product_module_allowed, get_allowed_case_product_modules
from app.core.pagination import paginate_query, paginated_response
from app.core.permissions import case_scope_check, user_has_permission
from app.models.case import Case
from app.models.support_ticket import SupportTicket, TicketCategory
from app.models.ticket_attachment import TicketAttachment
from app.models.user import User
from app.services import case_service, ticket_escalation_service as ticket_esc


def staff_may_see_ticket(db: Session, user: User, ticket: SupportTicket) -> bool:
    if user_has_permission(user, "admin.override"):
        return True
    if ticket.case_id:
        case = case_service.get_case(db, ticket.case_id)
        return bool(case and case_scope_check(db, user, case))
    if ticket.product_module and not case_product_module_allowed(user, ticket.product_module):
        return False
    return True


def list_tickets_for_user(
    db: Session,
    user: User,
    *,
    category: Optional[TicketCategory] = None,
    product_module: Optional[str] = None,
    page: int = 1,
    page_size: int = 25,
) -> dict:
    stmt = select(SupportTicket).order_by(SupportTicket.created_at.desc())

    if category:
        stmt = stmt.where(SupportTicket.category == category)
    if product_module:
        stmt = stmt.where(SupportTicket.product_module == product_module)

    if user_has_permission(user, "ticket.manage") or user_has_permission(user, "admin.override"):
        allowed = get_allowed_case_product_modules(user)
        if allowed is not None:
            if not allowed:
                stmt = stmt.where(SupportTicket.id < 0)
            else:
                stmt = stmt.where(
                    or_(
                        SupportTicket.case_id.is_(None),
                        SupportTicket.product_module.in_(allowed),
                        SupportTicket.product_module.is_(None),
                    )
                )
    else:
        stmt = stmt.where(SupportTicket.raised_by_user_id == user.id)

    rows, total = paginate_query(db, stmt, page=page, page_size=page_size)
    case_ids = {t.case_id for t in rows if t.case_id}
    cases_by_id: dict[int, Case] = {}
    if case_ids:
        cases = db.scalars(select(Case).where(Case.id.in_(case_ids))).all()
        cases_by_id = {c.id: c for c in cases}

    assignee_ids = {t.assigned_to_user_id for t in rows if t.assigned_to_user_id}
    raiser_ids = {t.raised_by_user_id for t in rows}
    user_ids = assignee_ids | raiser_ids
    users_by_id: dict[int, User] = {}
    if user_ids:
        for u in db.scalars(select(User).where(User.id.in_(user_ids))).all():
            users_by_id[u.id] = u

    ticket_ids = [t.id for t in rows]
    att_counts: dict[int, int] = {}
    if ticket_ids:
        counts = db.execute(
            select(TicketAttachment.ticket_id, func.count())
            .where(TicketAttachment.ticket_id.in_(ticket_ids))
            .group_by(TicketAttachment.ticket_id)
        ).all()
        att_counts = {tid: int(c) for tid, c in counts}

    items = []
    for t in rows:
        if t.case_id:
            case = cases_by_id.get(t.case_id)
            if case and not case_scope_check(db, user, case) and not user_has_permission(user, "admin.override"):
                continue
        elif t.product_module and not case_product_module_allowed(user, t.product_module):
            if not user_has_permission(user, "admin.override"):
                continue
        assignee = users_by_id.get(t.assigned_to_user_id) if t.assigned_to_user_id else None
        raiser = users_by_id.get(t.raised_by_user_id)
        items.append(
            _ticket_row(
                t,
                att_counts.get(t.id, 0),
                assignee=assignee,
                raiser=raiser,
                case=cases_by_id.get(t.case_id) if t.case_id else None,
            )
        )

    return paginated_response(items, total, page, page_size)


def _ticket_row(
    t: SupportTicket,
    attachment_count: int = 0,
    *,
    assignee: User | None = None,
    raiser: User | None = None,
    case: Case | None = None,
) -> dict:
    from app.services import case_service
    from app.services.ticket_participant_service import primary_portal_label, role_labels, user_summary

    row = {
        "id": t.id,
        "case_id": t.case_id,
        "product_module": t.product_module,
        "raised_by_user_id": t.raised_by_user_id,
        "raised_by_name": raiser.full_name if raiser else None,
        "raised_by_portal": primary_portal_label(list(raiser.role_names)) if raiser else None,
        "raised_by_role_labels": role_labels(list(raiser.role_names)) if raiser else [],
        "subject": t.subject,
        "body": t.body,
        "category": t.category.value,
        "topic": t.topic.value if t.topic else "OTHER",
        "topic_label": ticket_esc.TOPIC_LABELS.get(t.topic, "Other") if t.topic else "Other",
        "status": t.status.value,
        "assigned_to_user_id": t.assigned_to_user_id,
        "assigned_to_name": assignee.full_name if assignee else None,
        "assignee_role_labels": role_labels(list(assignee.role_names)) if assignee else [],
        "escalation_level": getattr(t, "escalation_level", 0) or 0,
        "attachment_count": attachment_count,
        "created_at": t.created_at.isoformat(),
        "updated_at": t.updated_at.isoformat(),
    }
    if case:
        row["case_code"] = case.case_code
        row["child_name"] = case_service.case_child_display_name(case)
    return row
