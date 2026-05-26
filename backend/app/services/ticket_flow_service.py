from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.permissions import user_has_permission
from app.models.support_ticket import SupportTicket, TicketMessage, TicketStatus
from app.models.user import User
from app.services import case_service, ticket_escalation_service as ticket_esc
from app.services.ticket_participant_service import primary_portal_label, role_label


def _is_staff(user: User) -> bool:
    return user_has_permission(user, "ticket.manage") or user_has_permission(user, "admin.override")


def _has_non_raiser_reply(db: Session, ticket: SupportTicket) -> bool:
    msgs = db.scalars(
        select(TicketMessage)
        .where(
            TicketMessage.ticket_id == ticket.id,
            TicketMessage.author_user_id != ticket.raised_by_user_id,
            TicketMessage.is_internal.is_(False),
        )
        .limit(1)
    ).first()
    return msgs is not None


def ticket_flow_flags(db: Session, user: User, ticket: SupportTicket) -> dict:
    roles = ticket_esc.escalation_roles(ticket.topic)
    level = ticket.escalation_level or 0
    max_level = len(roles) - 1
    is_raiser = ticket.raised_by_user_id == user.id
    staff = _is_staff(user)
    has_staff_reply = _has_non_raiser_reply(db, ticket)
    closed = ticket.status == TicketStatus.CLOSED

    can_escalate = (
        is_raiser
        and not closed
        and level < max_level
        and has_staff_reply
        and ticket.status in (TicketStatus.OPEN, TicketStatus.IN_PROGRESS, TicketStatus.RESOLVED)
    )
    can_escalate_staff = staff and not closed
    can_accept = is_raiser and ticket.status == TicketStatus.RESOLVED
    can_close_raiser = is_raiser and ticket.status in (
        TicketStatus.RESOLVED,
        TicketStatus.IN_PROGRESS,
    )
    can_resolve = staff and ticket.status not in (TicketStatus.CLOSED, TicketStatus.RESOLVED)
    can_close_staff = staff and ticket.status != TicketStatus.CLOSED
    can_reply = ticket.status != TicketStatus.CLOSED

    next_role = roles[level + 1] if level < max_level else None

    return {
        "is_raiser": is_raiser,
        "can_escalate": can_escalate,
        "can_escalate_staff": can_escalate_staff,
        "can_accept": can_accept,
        "can_close": can_close_raiser or can_close_staff,
        "can_close_raiser": can_close_raiser,
        "can_close_staff": can_close_staff,
        "can_resolve": can_resolve,
        "can_reply": can_reply,
        "has_staff_reply": has_staff_reply,
        "escalation_level": level,
        "escalation_max_level": max_level,
        "escalation_chain": roles,
        "escalation_next_role": next_role,
    }


def _add_system_message(
    db: Session,
    ticket: SupportTicket,
    author_user_id: int,
    body: str,
) -> TicketMessage:
    msg = TicketMessage(ticket_id=ticket.id, author_user_id=author_user_id, body=body)
    db.add(msg)
    db.flush()
    return msg


def resolve_ticket(
    db: Session,
    user: User,
    ticket: SupportTicket,
    *,
    note: str | None = None,
) -> None:
    if not _is_staff(user):
        raise ValueError("Only staff can resolve tickets")
    if ticket.status == TicketStatus.CLOSED:
        raise ValueError("Ticket is already closed")
    note_text = (note or "").strip()
    if not note_text:
        raise ValueError("A resolution message is required")
    ticket.status = TicketStatus.RESOLVED
    ticket.resolved_at = datetime.now(timezone.utc)
    _add_system_message(db, ticket, user.id, note_text)


def close_ticket(
    db: Session,
    user: User,
    ticket: SupportTicket,
    *,
    note: str | None = None,
    accept_resolution: bool = False,
) -> None:
    if ticket.status == TicketStatus.CLOSED:
        raise ValueError("Ticket is already closed")

    is_raiser = ticket.raised_by_user_id == user.id
    staff = _is_staff(user)

    if is_raiser:
        if accept_resolution and ticket.status != TicketStatus.RESOLVED:
            raise ValueError("Ticket is not ready to accept — wait for a resolution from support")
        if not accept_resolution and ticket.status not in (
            TicketStatus.RESOLVED,
            TicketStatus.IN_PROGRESS,
        ):
            raise ValueError("Ticket cannot be closed in its current state")
        if not accept_resolution and not (note or "").strip() and ticket.status == TicketStatus.IN_PROGRESS:
            raise ValueError("Please add a short note when closing this ticket")
        ticket.status = TicketStatus.CLOSED
        ticket.resolved_at = datetime.now(timezone.utc)
        if note and note.strip():
            ticket.parent_resolution_feedback = note.strip()
            prefix = "[Closed]" if accept_resolution else "[Closed by requester]"
            _add_system_message(db, ticket, user.id, f"{prefix} {note.strip()}")
        elif accept_resolution:
            _add_system_message(db, ticket, user.id, "[Closed] Resolution accepted.")
        return

    if staff:
        note_text = (note or "").strip()
        if not note_text:
            raise ValueError("A closing note is required")
        ticket.status = TicketStatus.CLOSED
        ticket.resolved_at = datetime.now(timezone.utc)
        body = note_text if note_text.startswith("[Closed]") else f"[Closed] {note_text}"
        _add_system_message(db, ticket, user.id, body)
        return

    raise ValueError("Not allowed to close this ticket")


def set_ticket_status(
    db: Session,
    user: User,
    ticket: SupportTicket,
    status: TicketStatus,
    *,
    note: str | None = None,
) -> None:
    if not _is_staff(user):
        raise ValueError("Only staff can change ticket status")
    if ticket.status == TicketStatus.CLOSED and status != TicketStatus.CLOSED:
        raise ValueError("Reopen closed tickets with a new message or escalate")
    if status == TicketStatus.RESOLVED:
        resolve_ticket(db, user, ticket, note=note)
        return
    if status == TicketStatus.CLOSED:
        close_ticket(db, user, ticket, note=note)
        return
    prev = ticket.status
    ticket.status = status
    if status == TicketStatus.IN_PROGRESS and prev == TicketStatus.OPEN:
        pass
    label = status.value.replace("_", " ").title()
    body = f"[Status] Changed to {label}."
    if note and note.strip():
        body = f"{body} {note.strip()}"
    _add_system_message(db, ticket, user.id, body)


def escalate_ticket_for_user(
    db: Session,
    user: User,
    ticket: SupportTicket,
    *,
    reason: str | None = None,
    target_role: str | None = None,
    assign_to_user_id: int | None = None,
) -> dict:
    flags = ticket_flow_flags(db, user, ticket)
    staff = _is_staff(user)
    if not flags["can_escalate"] and not flags.get("can_escalate_staff"):
        raise ValueError("Cannot escalate this ticket")

    case = case_service.get_case(db, ticket.case_id) if ticket.case_id else None

    if staff and (target_role or assign_to_user_id):
        if assign_to_user_id:
            target_user = db.get(User, assign_to_user_id)
            if not target_user or not target_user.is_active:
                raise ValueError("Selected user is not available")
            ticket.assigned_to_user_id = assign_to_user_id
            dest = f"{target_user.full_name} ({primary_portal_label(list(target_user.role_names))})"
        elif target_role:
            uid = ticket_esc.find_assignee_for_role(db, target_role, case)
            if not uid:
                raise ValueError(f"No active user found for {role_label(target_role)}")
            ticket.assigned_to_user_id = uid
            target_user = db.get(User, uid)
            dest = f"{target_user.full_name if target_user else role_label(target_role)} ({role_label(target_role)})"
        else:
            dest = "support"
        roles = ticket_esc.escalation_roles(ticket.topic)
        ticket.escalation_level = min((ticket.escalation_level or 0) + 1, max(len(roles) - 1, 0))
        ticket.status = TicketStatus.IN_PROGRESS
        extra = f" Reason: {reason.strip()}" if reason and reason.strip() else ""
        _add_system_message(
            db,
            ticket,
            user.id,
            f"[Escalated] Assigned to {dest}.{extra}",
        )
        return {"assigned_to_user_id": ticket.assigned_to_user_id, "escalation_level": ticket.escalation_level}

    result = ticket_esc.escalate_ticket(db, ticket, case)
    if result.get("max_level"):
        raise ValueError("Already at highest escalation level")

    roles = ticket_esc.escalation_roles(ticket.topic)
    level = ticket.escalation_level or 0
    role_label = roles[level] if level < len(roles) else "support"
    who = "Staff" if _is_staff(user) and user.id != ticket.raised_by_user_id else "Requester"
    extra = f" Reason: {reason.strip()}" if reason and reason.strip() else ""
    _add_system_message(
        db,
        ticket,
        user.id,
        f"[Escalated] {who} escalated to level {level} ({role_label.replace('_', ' ')}).{extra}",
    )
    return result


def reopen_ticket_by_raiser(
    db: Session,
    user: User,
    ticket: SupportTicket,
    *,
    note: str,
) -> None:
    if ticket.raised_by_user_id != user.id:
        raise ValueError("Only the person who raised this ticket can reopen it")
    if ticket.status != TicketStatus.RESOLVED:
        raise ValueError("Only resolved tickets can be reopened")
    text = (note or "").strip()
    if not text:
        raise ValueError("Please describe why you are reopening this ticket")
    ticket.status = TicketStatus.IN_PROGRESS
    ticket.resolved_at = None
    _add_system_message(db, ticket, user.id, f"[Reopened] {text}")


def on_ticket_message(
    db: Session,
    user: User,
    ticket: SupportTicket,
) -> None:
    """Status transitions when a new public message is added."""
    if ticket.status == TicketStatus.CLOSED:
        return
    if user.id == ticket.raised_by_user_id:
        if ticket.status == TicketStatus.RESOLVED:
            ticket.status = TicketStatus.IN_PROGRESS
            ticket.resolved_at = None
            _add_system_message(
                db,
                ticket,
                user.id,
                "[Reopened] Requester replied after resolution — ticket is open again.",
            )
        return
    if _is_staff(user) or user.id != ticket.raised_by_user_id:
        if ticket.status == TicketStatus.OPEN:
            ticket.status = TicketStatus.IN_PROGRESS
