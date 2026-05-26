from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.permissions import user_has_permission
from app.models.support_ticket import SupportTicket, TicketMessage
from app.models.user import User
from app.services import case_service, ticket_attachment_service as att_svc
from app.services import ticket_escalation_service as ticket_esc
from app.services import ticket_flow_service as flow
from app.services import ticket_list_service
from app.services.ticket_participant_service import ESCALATION_TARGET_ROLES, user_summary


def _can_view_ticket(db: Session, user: User, ticket: SupportTicket) -> bool:
    if ticket.raised_by_user_id == user.id:
        return True
    if att_svc.can_access_ticket(db, user, ticket):
        return True
    if user_has_permission(user, "ticket.manage") or user_has_permission(user, "admin.override"):
        return ticket_list_service.staff_may_see_ticket(db, user, ticket)
    return False


def get_ticket_detail(db: Session, user: User, ticket_id: int) -> dict:
    ticket = db.get(SupportTicket, ticket_id)
    if not ticket or not _can_view_ticket(db, user, ticket):
        raise HTTPException(status_code=404, detail="Ticket not found")

    raiser = db.get(User, ticket.raised_by_user_id)
    assignee = db.get(User, ticket.assigned_to_user_id) if ticket.assigned_to_user_id else None
    case = case_service.get_case(db, ticket.case_id) if ticket.case_id else None
    row = ticket_list_service._ticket_row(
        ticket,
        att_svc.count_for_ticket(db, ticket.id),
        assignee=assignee,
        raiser=raiser,
        case=case,
    )

    attachments = att_svc.list_for_ticket(db, ticket.id)
    ticket_level = [att_svc.attachment_to_dict(a) for a in attachments if a.message_id is None]

    msg_stmt = select(TicketMessage).where(TicketMessage.ticket_id == ticket.id).order_by(TicketMessage.created_at.asc())
    if ticket.raised_by_user_id == user.id:
        msg_stmt = msg_stmt.where(TicketMessage.is_internal.is_(False))
    msgs = db.scalars(msg_stmt).all()
    if len(msgs) > 50:
        msgs = msgs[-50:]
    by_message: dict[int | None, list] = {}
    for a in attachments:
        by_message.setdefault(a.message_id, []).append(att_svc.attachment_to_dict(a))

    messages = []
    for m in msgs:
        author = db.get(User, m.author_user_id)
        messages.append(
            {
                "id": m.id,
                "body": m.body,
                "author_user_id": m.author_user_id,
                "author_name": author.full_name if author else "Staff",
                "is_raiser": m.author_user_id == ticket.raised_by_user_id,
                "is_internal": bool(getattr(m, "is_internal", False)),
                "created_at": m.created_at.isoformat(),
                "attachments": by_message.get(m.id, []),
            }
        )

    row["messages"] = messages
    row["attachments"] = ticket_level
    row["topic_label"] = ticket_esc.TOPIC_LABELS.get(ticket.topic, "Other") if ticket.topic else "Other"
    row["category_label"] = ticket.category.value.replace("_", " ").title() if ticket.category else "Other"
    row["raised_by"] = user_summary(raiser)
    row["assignee"] = user_summary(assignee)
    row["escalation_targets"] = [{"role": r, "label": lbl} for r, lbl in ESCALATION_TARGET_ROLES]
    row.update(flow.ticket_flow_flags(db, user, ticket))
    row["resolved_at"] = ticket.resolved_at.isoformat() if ticket.resolved_at else None
    row["parent_satisfaction_rating"] = ticket.parent_satisfaction_rating
    row["parent_resolution_feedback"] = ticket.parent_resolution_feedback
    return row
