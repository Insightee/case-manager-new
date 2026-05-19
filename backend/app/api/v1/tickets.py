from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_request_meta
from app.core.audit import log_audit
from app.core.database import get_db
from app.core.module_access import case_product_module_allowed
from app.core.permissions import case_scope_check, require_permission, user_has_permission
from app.models.case import Case
from app.models.support_ticket import SupportTicket, TicketCategory, TicketMessage, TicketStatus
from app.models.user import User
from app.services import case_service

router = APIRouter(prefix="/tickets", tags=["tickets"])


class TicketCreate(BaseModel):
    case_id: Optional[int] = None
    subject: str
    body: str
    product_module: Optional[str] = None
    category: TicketCategory = TicketCategory.OTHER


class TicketMessageCreate(BaseModel):
    body: str


class TicketUpdate(BaseModel):
    status: Optional[TicketStatus] = None
    assigned_to_user_id: Optional[int] = None


@router.get("")
def list_tickets(
    category: Optional[TicketCategory] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tickets = db.scalars(select(SupportTicket).order_by(SupportTicket.created_at.desc())).all()
    result = []
    for t in tickets:
        if t.case_id:
            case = case_service.get_case(db, t.case_id)
            if case and not case_scope_check(db, user, case) and not user_has_permission(user, "admin.override"):
                continue
        elif t.product_module and not case_product_module_allowed(user, t.product_module):
            if not user_has_permission(user, "admin.override"):
                continue
        if not user_has_permission(user, "ticket.manage") and t.raised_by_user_id != user.id:
            continue
        if category and t.category != category:
            continue
        result.append({
            "id": t.id,
            "case_id": t.case_id,
            "raised_by_user_id": t.raised_by_user_id,
            "subject": t.subject,
            "body": t.body,
            "category": t.category.value,
            "status": t.status.value,
            "assigned_to_user_id": t.assigned_to_user_id,
            "created_at": t.created_at.isoformat(),
            "updated_at": t.updated_at.isoformat(),
        })
    return result


@router.post("", status_code=status.HTTP_201_CREATED)
def create_ticket(
    payload: TicketCreate,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    assigned_to = None
    if payload.case_id:
        case = case_service.get_case(db, payload.case_id)
        if case:
            assigned_to = case.case_manager_user_id
    ticket = SupportTicket(
        case_id=payload.case_id,
        raised_by_user_id=user.id,
        assigned_to_user_id=assigned_to,
        product_module=payload.product_module,
        category=payload.category,
        subject=payload.subject,
        body=payload.body,
    )
    db.add(ticket)
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="create", entity_type="support_ticket", entity_id=ticket.id, **meta)
    db.commit()
    db.refresh(ticket)
    return {"id": ticket.id, "status": ticket.status.value}


@router.patch("/{ticket_id}")
def update_ticket(
    ticket_id: int,
    payload: TicketUpdate,
    request: Request,
    user: User = Depends(require_permission("ticket.manage")),
    db: Session = Depends(get_db),
):
    ticket = db.get(SupportTicket, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    if payload.status:
        ticket.status = payload.status
    if payload.assigned_to_user_id is not None:
        ticket.assigned_to_user_id = payload.assigned_to_user_id
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="update", entity_type="support_ticket", entity_id=ticket.id, **meta)
    db.commit()
    return {"id": ticket.id, "status": ticket.status.value}


@router.post("/{ticket_id}/messages")
def add_message(
    ticket_id: int,
    payload: TicketMessageCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ticket = db.get(SupportTicket, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    msg = TicketMessage(ticket_id=ticket_id, author_user_id=user.id, body=payload.body)
    db.add(msg)
    db.commit()
    return {"id": msg.id}
