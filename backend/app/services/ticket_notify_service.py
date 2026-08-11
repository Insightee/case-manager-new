from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.departments import staff_department_label
from app.models.support_ticket import SupportTicket
from app.models.user import User
from app.services import notification_service


def _ticket_url(ticket_id: int) -> str:
    base = settings.frontend_url.rstrip("/")
    return f"{base}/admin/support?ticket={ticket_id}"


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


def notify_ticket_escalated_to_user(
    db: Session,
    ticket: SupportTicket,
    *,
    assignee_user_id: int,
    actor_user_id: int,
    actor: User | None = None,
    background_tasks=None,
) -> None:
    if not assignee_user_id or assignee_user_id == actor_user_id:
        return
    subject = (ticket.subject or "Support ticket")[:80]
    actor_name = actor.full_name if actor else "A colleague"
    notification_service.create_notification(
        db,
        user_id=assignee_user_id,
        title=f"Ticket escalated to you: {subject}",
        body=f"{actor_name} escalated a support ticket to you. Open Support → Tickets to respond.",
        entity_type="support_ticket",
        entity_id=ticket.id,
    )
    assignee = db.get(User, assignee_user_id)
    if assignee and background_tasks is not None:
        from app.services.email.events import EmailEvent
        from app.services.email.service import enqueue_ticket_escalated_email

        enqueue_ticket_escalated_email(
            background_tasks,
            db,
            to=assignee.email,
            full_name=assignee.full_name,
            ticket_subject=subject,
            ticket_url=_ticket_url(ticket.id),
            actor_name=actor_name,
            department_label=None,
            entity_id=ticket.id,
            event=EmailEvent.TICKET_ESCALATED,
        )


def notify_ticket_escalated_to_department(
    db: Session,
    ticket: SupportTicket,
    *,
    user_ids: list[int],
    actor_user_id: int,
    department_id: str,
    actor: User | None = None,
    background_tasks=None,
) -> None:
    if not user_ids:
        return
    subject = (ticket.subject or "Support ticket")[:80]
    dept_label = staff_department_label(department_id) or department_id.replace("_", " ").title()
    actor_name = actor.full_name if actor else "A colleague"
    for uid in user_ids:
        if uid == actor_user_id:
            continue
        notification_service.create_notification(
            db,
            user_id=uid,
            title=f"Ticket escalated to {dept_label}: {subject}",
            body=(
                f"{actor_name} escalated a ticket to the {dept_label} queue. "
                "Anyone in your department can pick it up in Support → Tickets."
            ),
            entity_type="support_ticket",
            entity_id=ticket.id,
        )
        member = db.get(User, uid)
        if member and background_tasks is not None:
            from app.services.email.events import EmailEvent
            from app.services.email.service import enqueue_ticket_escalated_email

            enqueue_ticket_escalated_email(
                background_tasks,
                db,
                to=member.email,
                full_name=member.full_name,
                ticket_subject=subject,
                ticket_url=_ticket_url(ticket.id),
                actor_name=actor_name,
                department_label=dept_label,
                entity_id=ticket.id,
                event=EmailEvent.TICKET_ESCALATED,
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
