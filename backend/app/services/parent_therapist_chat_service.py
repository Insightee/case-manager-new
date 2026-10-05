from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.assignment import CaseAssignment, CaseAssignmentStatus
from app.models.case import Case
from app.models.support_ticket import SupportTicket, TicketCategory, TicketMessage, TicketStatus, TicketTopic
from app.models.user import User
from app.services import case_service, notification_service, parent_ticket_service

THERAPIST_CHAT_SUBJECT = "Therapist chat"


def _active_therapist_user_id(db: Session, case: Case) -> int | None:
    asg = db.scalars(
        select(CaseAssignment)
        .where(
            CaseAssignment.case_id == case.id,
            CaseAssignment.status == CaseAssignmentStatus.ACTIVE,
        )
        .order_by(CaseAssignment.start_date.desc())
    ).first()
    if not asg:
        return None
    therapist = db.get(User, asg.therapist_user_id)
    if not therapist or not therapist.is_active:
        return None
    return therapist.id


def _find_open_chat(db: Session, parent_user_id: int, case_id: int) -> SupportTicket | None:
    return db.scalars(
        select(SupportTicket)
        .where(
            SupportTicket.raised_by_user_id == parent_user_id,
            SupportTicket.case_id == case_id,
            SupportTicket.subject == THERAPIST_CHAT_SUBJECT,
            SupportTicket.topic == TicketTopic.OTHER,
            SupportTicket.status.in_([TicketStatus.OPEN, TicketStatus.IN_PROGRESS]),
        )
        .order_by(SupportTicket.created_at.desc())
    ).first()


def ensure_therapist_chat(db: Session, user: User, case_id: int) -> dict:
    case = case_service.get_case(db, case_id)
    if not case:
        raise ValueError("Case not found")
    therapist_id = _active_therapist_user_id(db, case)
    if not therapist_id:
        raise ValueError("Your care team has not assigned a therapist yet — try again soon or use Support for help.")

    existing = _find_open_chat(db, user.id, case_id)
    if existing:
        return parent_ticket_service.get_parent_ticket(db, user, existing.id)

    ticket = SupportTicket(
        case_id=case_id,
        raised_by_user_id=user.id,
        assigned_to_user_id=therapist_id,
        topic=TicketTopic.OTHER,
        category=TicketCategory.SERVICE,
        subject=THERAPIST_CHAT_SUBJECT,
        body="Therapist chat started.",
        status=TicketStatus.OPEN,
        product_module=case.product_module,
    )
    db.add(ticket)
    db.flush()
    return parent_ticket_service.get_parent_ticket(db, user, ticket.id)


def loop_in_case_manager(
    db: Session,
    user: User,
    ticket_id: int,
    *,
    note: str | None = None,
) -> dict:
    ticket = db.get(SupportTicket, ticket_id)
    if not ticket or ticket.raised_by_user_id != user.id:
        raise ValueError("Chat not found")
    if ticket.subject != THERAPIST_CHAT_SUBJECT:
        raise ValueError("This action is only for therapist chat")

    case = case_service.get_case(db, ticket.case_id) if ticket.case_id else None
    if not case or not case.case_manager_user_id:
        raise ValueError("No case manager is assigned on this case yet.")

    cm = db.get(User, case.case_manager_user_id)
    if not cm or not cm.is_active:
        raise ValueError("Case manager is not available right now.")

    child = case.child.full_name if case.child else "your child"
    parent_name = user.full_name or "Parent"
    snippet = (note or "").strip()
    body = f"{parent_name} asked to loop in the case manager for {child}."
    if snippet:
        body = f"{body}\n\n{snippet}"

    db.add(TicketMessage(ticket_id=ticket.id, author_user_id=user.id, body=body))
    notification_service.create_notification(
        db,
        user_id=cm.id,
        title="Parent chat — case manager loop-in",
        body=f"{parent_name} added you to the therapist chat for {child}.",
        entity_type="support_ticket",
        entity_id=ticket.id,
        dedupe_key=f"therapist_chat_loop_in:{ticket.id}:{cm.id}",
    )
    db.flush()
    return parent_ticket_service.get_parent_ticket(db, user, ticket.id)
