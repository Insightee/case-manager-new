from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.support_ticket import SupportTicket
from app.models.user import User
from app.services import notification_service


def notify_ticket_assigned(
    db: Session,
    ticket: SupportTicket,
    *,
    assignee_user_id: int,
    actor_user_id: int,
) -> None:
    if not assignee_user_id or assignee_user_id == actor_user_id:
        return
    subject = (ticket.subject or "Support ticket")[:80]
    notification_service.create_notification(
        db,
        user_id=assignee_user_id,
        title=f"Ticket assigned: {subject}",
        body="A support ticket was assigned to you. Open Support → Tickets to respond.",
        entity_type="support_ticket",
        entity_id=ticket.id,
    )


def notify_ticket_reopened(
    db: Session,
    ticket: SupportTicket,
    *,
    actor_user_id: int,
) -> None:
    if not ticket.assigned_to_user_id or ticket.assigned_to_user_id == actor_user_id:
        return
    subject = (ticket.subject or "Support ticket")[:80]
    notification_service.create_notification(
        db,
        user_id=ticket.assigned_to_user_id,
        title=f"Ticket reopened: {subject}",
        body="The requester reopened this ticket. Please review the latest message.",
        entity_type="support_ticket",
        entity_id=ticket.id,
    )
