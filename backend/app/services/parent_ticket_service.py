from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.case import Case
from app.models.support_ticket import SupportTicket, TicketMessage, TicketStatus, TicketTopic
from app.models.user import User
from app.services import case_service, ticket_attachment_service as att_svc, ticket_escalation_service as esc


def _ticket_visible(db: Session, user: User, ticket: SupportTicket) -> bool:
    if ticket.raised_by_user_id == user.id:
        return True
    return False


def ticket_to_dict(db: Session, ticket: SupportTicket, *, include_messages: bool = False) -> dict:
    case = case_service.get_case(db, ticket.case_id) if ticket.case_id else None
    child_name = case.child.full_name if case and case.child else None
    assignee = db.get(User, ticket.assigned_to_user_id) if ticket.assigned_to_user_id else None
    roles = esc.escalation_roles(ticket.topic)
    data = {
        "id": ticket.id,
        "case_id": ticket.case_id,
        "case_code": case.case_code if case else None,
        "child_name": child_name,
        "topic": ticket.topic.value,
        "topic_label": esc.TOPIC_LABELS.get(ticket.topic, ticket.topic.value),
        "subject": ticket.subject,
        "body": ticket.body,
        "category": ticket.category.value,
        "status": ticket.status.value,
        "escalation_level": ticket.escalation_level or 0,
        "escalation_max_level": len(roles) - 1,
        "escalation_chain": roles,
        "assigned_to_name": assignee.full_name if assignee else None,
        "parent_satisfaction_rating": ticket.parent_satisfaction_rating,
        "parent_resolution_feedback": ticket.parent_resolution_feedback,
        "resolved_at": ticket.resolved_at.isoformat() if ticket.resolved_at else None,
        "created_at": ticket.created_at.isoformat(),
        "updated_at": ticket.updated_at.isoformat(),
        "can_escalate": (ticket.escalation_level or 0) < len(roles) - 1
        and ticket.status not in (TicketStatus.CLOSED,),
        "can_rate": ticket.status in (TicketStatus.RESOLVED, TicketStatus.CLOSED)
        and ticket.parent_satisfaction_rating is None,
        "can_accept": ticket.status == TicketStatus.RESOLVED,
        "attachment_count": att_svc.count_for_ticket(db, ticket.id),
    }
    attachments = att_svc.list_for_ticket(db, ticket.id)
    data["attachments"] = [att_svc.attachment_to_dict(a) for a in attachments if a.message_id is None]
    if include_messages:
        msgs = db.scalars(
            select(TicketMessage)
            .where(TicketMessage.ticket_id == ticket.id)
            .order_by(TicketMessage.created_at.asc())
        ).all()
        by_message: dict[int | None, list] = {}
        for a in attachments:
            by_message.setdefault(a.message_id, []).append(att_svc.attachment_to_dict(a))
        data["messages"] = [
            {
                "id": m.id,
                "body": m.body,
                "author_name": (db.get(User, m.author_user_id).full_name if db.get(User, m.author_user_id) else "Staff"),
                "is_parent": m.author_user_id == ticket.raised_by_user_id,
                "created_at": m.created_at.isoformat(),
                "attachments": by_message.get(m.id, []),
            }
            for m in msgs
        ]
    return data


def list_parent_tickets(db: Session, user: User) -> list[dict]:
    tickets = db.scalars(
        select(SupportTicket)
        .where(SupportTicket.raised_by_user_id == user.id)
        .order_by(SupportTicket.created_at.desc())
    ).all()
    return [ticket_to_dict(db, t) for t in tickets]


def get_parent_ticket(db: Session, user: User, ticket_id: int) -> dict:
    ticket = db.get(SupportTicket, ticket_id)
    if not ticket or not _ticket_visible(db, user, ticket):
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket_to_dict(db, ticket, include_messages=True)
