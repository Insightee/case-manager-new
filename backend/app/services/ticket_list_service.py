"""Paginated staff ticket listing with SQL scoping."""
from __future__ import annotations

from typing import Optional

from sqlalchemy import exists, func, or_, select
from sqlalchemy.orm import Session

from app.core.module_access import get_allowed_case_product_modules
from app.core.pagination import paginate_query, paginated_response
from app.core.permissions import user_has_permission
from app.models.assignment import CaseAssignment, CaseAssignmentStatus
from app.models.case import Case
from app.models.child import Child
from app.models.parent import ParentGuardian, parent_child_link
from app.models.support_ticket import SupportTicket, TicketCategory, TicketStatus
from app.models.ticket_attachment import TicketAttachment
from app.models.user import User
from app.services import case_service, ticket_escalation_service as ticket_esc
from app.core.support_status import canonical_ticket_status, ticket_status_predicate
from app.services.support_access_service import (
    is_team_scoped_support_user,
    may_read_support_ticket,
    support_scope,
    team_support_ticket_clause,
)


def staff_may_see_ticket(db: Session, user: User, ticket: SupportTicket) -> bool:
    return may_read_support_ticket(db, user, ticket)


def _apply_ticket_search(stmt, search: str | None):
    """Filter tickets by subject, id, case/client/parent/therapist names, or raiser/assignee."""
    q = (search or "").strip()
    if not q:
        return stmt
    pattern = f"%{q}%"
    child_full = func.trim(Child.first_name + " " + Child.last_name)
    clauses = [
        SupportTicket.subject.ilike(pattern),
        SupportTicket.body.ilike(pattern),
    ]
    if q.isdigit():
        clauses.append(SupportTicket.id == int(q))

    case_match = exists(
        select(Case.id)
        .outerjoin(Child, Child.id == Case.child_id)
        .where(
            Case.id == SupportTicket.case_id,
            or_(
                Case.case_code.ilike(pattern),
                Child.first_name.ilike(pattern),
                Child.last_name.ilike(pattern),
                child_full.ilike(pattern),
                exists(
                    select(CaseAssignment.id)
                    .join(User, User.id == CaseAssignment.therapist_user_id)
                    .where(
                        CaseAssignment.case_id == Case.id,
                        CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
                        User.full_name.ilike(pattern),
                    )
                ),
                exists(
                    select(parent_child_link.c.child_id)
                    .join(ParentGuardian, ParentGuardian.id == parent_child_link.c.parent_guardian_id)
                    .join(User, User.id == ParentGuardian.user_id)
                    .where(
                        parent_child_link.c.child_id == Child.id,
                        User.full_name.ilike(pattern),
                    )
                ),
            ),
        )
    )
    clauses.append(case_match)

    raiser_match = exists(
        select(User.id).where(
            User.id == SupportTicket.raised_by_user_id,
            User.full_name.ilike(pattern),
        )
    )
    clauses.append(raiser_match)

    assignee_match = exists(
        select(User.id).where(
            User.id == SupportTicket.assigned_to_user_id,
            User.full_name.ilike(pattern),
        )
    )
    clauses.append(assignee_match)

    return stmt.where(or_(*clauses))


def list_tickets_for_user(
    db: Session,
    user: User,
    *,
    category: Optional[TicketCategory] = None,
    product_module: Optional[str] = None,
    case_id: Optional[int] = None,
    status: Optional[TicketStatus] = None,
    canonical_status: Optional[str] = None,
    search: Optional[str] = None,
    page: int = 1,
    page_size: int = 25,
) -> dict:
    stmt = select(SupportTicket).order_by(
        SupportTicket.created_at.desc(),
        SupportTicket.id.desc(),
    )

    if category:
        stmt = stmt.where(SupportTicket.category == category)
    if product_module:
        stmt = stmt.where(SupportTicket.product_module == product_module)
    if case_id is not None:
        stmt = stmt.where(SupportTicket.case_id == case_id)
    if canonical_status:
        predicate = ticket_status_predicate(canonical_status)
        if predicate is not None:
            stmt = stmt.where(predicate)
    elif status:
        stmt = stmt.where(SupportTicket.status == status)
    stmt = _apply_ticket_search(stmt, search)

    scope = support_scope(user, db)
    scope_clause = None
    if scope == "none":
        scope_clause = SupportTicket.raised_by_user_id == user.id
    elif scope == "finance_desk":
        scope_clause = ticket_esc.finance_desk_ticket_clause(user.id)
    elif scope == "hr_desk":
        scope_clause = ticket_esc.hr_desk_ticket_clause(user.id)
    elif scope == "admin_desk":
        scope_clause = ticket_esc.admin_desk_ticket_clause(user.id)
    elif user_has_permission(user, "ticket.manage") or user_has_permission(user, "admin.override"):
        if is_team_scoped_support_user(user):
            scope_clause = team_support_ticket_clause(user)
        else:
            allowed = get_allowed_case_product_modules(user)
            if allowed is not None:
                if not allowed:
                    scope_clause = SupportTicket.id < 0
                else:
                    scope_clause = or_(
                        SupportTicket.case_id.is_(None),
                        SupportTicket.product_module.in_(allowed),
                        SupportTicket.product_module.is_(None),
                    )
    else:
        scope_clause = SupportTicket.raised_by_user_id == user.id

    department_clause = None
    if scope != "full" and user.department and user_has_permission(user, "ticket.manage"):
        department_clause = SupportTicket.escalated_to_department == user.department
    if scope_clause is not None and department_clause is not None:
        stmt = stmt.where(or_(scope_clause, department_clause))
    elif scope_clause is not None:
        stmt = stmt.where(scope_clause)
    elif department_clause is not None:
        stmt = stmt.where(department_clause)

    rows, total = paginate_query(db, stmt, page=page, page_size=page_size)
    case_ids = {t.case_id for t in rows if t.case_id}
    cases_by_id: dict[int, Case] = {}
    therapist_by_case: dict[int, str] = {}
    if case_ids:
        case_id_list = list(case_ids)
        cases = db.scalars(select(Case).where(Case.id.in_(case_id_list))).all()
        cases_by_id = {c.id: c for c in cases}
        therapist_by_case = case_service._active_therapist_names(db, case_id_list)

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
        if not staff_may_see_ticket(db, user, t):
            continue
        assignee = users_by_id.get(t.assigned_to_user_id) if t.assigned_to_user_id else None
        raiser = users_by_id.get(t.raised_by_user_id)
        case = cases_by_id.get(t.case_id) if t.case_id else None
        items.append(
            _ticket_row(
                t,
                att_counts.get(t.id, 0),
                assignee=assignee,
                raiser=raiser,
                case=case,
                therapist_name=therapist_by_case.get(t.case_id) if t.case_id else None,
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
    therapist_name: str | None = None,
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
        "canonical_status": canonical_ticket_status(
            t.status, escalated_to_department=getattr(t, "escalated_to_department", None)
        ),
        "assigned_to_user_id": t.assigned_to_user_id,
        "assigned_to_name": assignee.full_name if assignee else None,
        "assignee_role_labels": role_labels(list(assignee.role_names)) if assignee else [],
        "escalated_to_department": getattr(t, "escalated_to_department", None),
        "escalation_level": getattr(t, "escalation_level", 0) or 0,
        "attachment_count": attachment_count,
        "created_at": t.created_at.isoformat(),
        "updated_at": t.updated_at.isoformat(),
    }
    if case:
        row["case_code"] = case.case_code
        row["child_name"] = case_service.case_child_display_name(case)
        row["therapist_name"] = therapist_name
    else:
        row["therapist_name"] = None
    return row
