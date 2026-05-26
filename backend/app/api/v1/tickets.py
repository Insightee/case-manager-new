from __future__ import annotations

import json
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_request_meta
from app.core.audit import log_audit
from app.core.database import get_db
from app.core.module_write import ensure_feature_write_access
from app.core.permissions import require_mutation_permission, require_permission, user_has_permission
from app.models.support_ticket import SupportTicket, TicketCategory, TicketMessage, TicketStatus, TicketTopic
from app.models.user import User
from app.services import (
    case_service,
    ticket_attachment_service as att_svc,
    ticket_detail_service,
    ticket_escalation_service as ticket_esc,
    ticket_flow_service as ticket_flow,
    ticket_list_service,
)

router = APIRouter(prefix="/tickets", tags=["tickets"])


def _guard_ticket_staff_write(user: User, ticket: SupportTicket, db: Session) -> None:
    if not (
        user_has_permission(user, "ticket.manage")
        or user_has_permission(user, "admin.override")
    ):
        return
    ensure_feature_write_access(user, "tickets", product_module=ticket.product_module, db=db)


class TicketCreate(BaseModel):
    case_id: Optional[int] = None
    subject: str
    body: str
    product_module: Optional[str] = None
    category: TicketCategory = TicketCategory.OTHER
    topic: Optional[str] = None


class TicketCreatedOut(BaseModel):
    id: int
    subject: str
    category: str
    status: str
    created_at: str


class TicketMessageCreate(BaseModel):
    body: str
    is_internal: bool = False


class TicketUpdate(BaseModel):
    status: Optional[TicketStatus] = None
    assigned_to_user_id: Optional[int] = None


class TicketFlowNote(BaseModel):
    note: Optional[str] = None
    accept_resolution: bool = False


class TicketEscalateRequest(BaseModel):
    reason: Optional[str] = None
    target_role: Optional[str] = None
    assign_to_user_id: Optional[int] = None


def _parse_category(raw: str) -> TicketCategory:
    try:
        return TicketCategory(raw.upper())
    except ValueError:
        return TicketCategory.OTHER


@router.get("")
def list_tickets(
    category: Optional[TicketCategory] = None,
    product_module: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ticket_list_service.list_tickets_for_user(
        db, user, category=category, product_module=product_module, page=page, page_size=page_size
    )


@router.get("/attachments/{attachment_id}/download")
def download_ticket_attachment(
    attachment_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    att = att_svc.get_attachment_or_404(db, attachment_id)
    if not att_svc.can_access_attachment(db, user, att):
        raise HTTPException(status_code=404, detail="Attachment not found")
    return att_svc.download_response(att)


@router.get("/{ticket_id}")
def get_ticket(
    ticket_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ticket_detail_service.get_ticket_detail(db, user, ticket_id)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_ticket(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    content_type = request.headers.get("content-type", "")
    files: List[UploadFile] = []
    if "multipart/form-data" in content_type:
        form = await request.form()
        subject = str(form.get("subject") or "").strip()
        body = str(form.get("body") or "").strip()
        if not subject or not body:
            raise HTTPException(status_code=400, detail="subject and body are required")
        category = _parse_category(str(form.get("category") or "OTHER"))
        case_id_raw = form.get("case_id")
        case_id = int(case_id_raw) if case_id_raw not in (None, "") else None
        product_module = str(form.get("product_module") or "") or None
        topic_raw = str(form.get("topic") or "") or None
        files = att_svc.files_from_form(form)
    else:
        try:
            data = await request.json()
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid JSON body")
        payload = TicketCreate(**data)
        subject = payload.subject.strip()
        body = payload.body.strip()
        category = payload.category
        case_id = payload.case_id
        product_module = payload.product_module
        topic_raw = payload.topic

    case = case_service.get_case(db, case_id) if case_id else None
    topic_enum = ticket_esc.topic_from_str(topic_raw) if topic_raw else TicketTopic.OTHER
    ticket = SupportTicket(
        case_id=case_id,
        raised_by_user_id=user.id,
        product_module=product_module or (case.product_module if case else None),
        category=category,
        topic=topic_enum,
        subject=subject,
        body=body,
    )
    ticket_esc.assign_ticket(db, ticket, case)
    db.add(ticket)
    db.flush()
    msg = TicketMessage(ticket_id=ticket.id, author_user_id=user.id, body=body)
    db.add(msg)
    db.flush()
    try:
        await att_svc.save_attachments(db, ticket, user, files, message_id=None)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="create", entity_type="support_ticket", entity_id=ticket.id, **meta)
    db.commit()
    db.refresh(ticket)
    return TicketCreatedOut(
        id=ticket.id,
        subject=ticket.subject,
        category=ticket.category.value,
        status=ticket.status.value,
        created_at=ticket.created_at.isoformat() if ticket.created_at else "",
    )


@router.patch("/{ticket_id}")
def update_ticket(
    ticket_id: int,
    payload: TicketUpdate,
    request: Request,
    user: User = Depends(require_mutation_permission("ticket.manage")),
    db: Session = Depends(get_db),
):
    ticket = db.get(SupportTicket, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    _guard_ticket_staff_write(user, ticket, db)
    if payload.status:
        try:
            ticket_flow.set_ticket_status(db, user, ticket, payload.status)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    prev_assignee = ticket.assigned_to_user_id
    if payload.assigned_to_user_id is not None:
        ticket.assigned_to_user_id = payload.assigned_to_user_id
        if ticket.assigned_to_user_id and ticket.assigned_to_user_id != prev_assignee:
            from app.services import ticket_notify_service as ticket_notify

            ticket_notify.notify_ticket_assigned(
                db,
                ticket,
                assignee_user_id=ticket.assigned_to_user_id,
                actor_user_id=user.id,
            )
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="update", entity_type="support_ticket", entity_id=ticket.id, **meta)
    db.commit()
    return ticket_detail_service.get_ticket_detail(db, user, ticket.id)


@router.post("/{ticket_id}/resolve")
def resolve_ticket_endpoint(
    ticket_id: int,
    payload: TicketFlowNote,
    request: Request,
    user: User = Depends(require_mutation_permission("ticket.manage")),
    db: Session = Depends(get_db),
):
    ticket = db.get(SupportTicket, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    _guard_ticket_staff_write(user, ticket, db)
    try:
        ticket_flow.resolve_ticket(db, user, ticket, note=payload.note)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="resolve", entity_type="support_ticket", entity_id=ticket.id, **meta)
    db.commit()
    return ticket_detail_service.get_ticket_detail(db, user, ticket.id)


@router.post("/{ticket_id}/close")
def close_ticket_endpoint(
    ticket_id: int,
    payload: TicketFlowNote,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ticket = db.get(SupportTicket, ticket_id)
    if not ticket or not ticket_detail_service._can_view_ticket(db, user, ticket):
        raise HTTPException(status_code=404, detail="Ticket not found")
    try:
        ticket_flow.close_ticket(
            db,
            user,
            ticket,
            note=payload.note,
            accept_resolution=payload.accept_resolution,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="close", entity_type="support_ticket", entity_id=ticket.id, **meta)
    db.commit()
    return ticket_detail_service.get_ticket_detail(db, user, ticket.id)


@router.post("/{ticket_id}/escalate")
def escalate_ticket_endpoint(
    ticket_id: int,
    request: Request,
    payload: TicketEscalateRequest = TicketEscalateRequest(),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ticket = db.get(SupportTicket, ticket_id)
    if not ticket or not ticket_detail_service._can_view_ticket(db, user, ticket):
        raise HTTPException(status_code=404, detail="Ticket not found")
    prev_assignee = ticket.assigned_to_user_id
    try:
        ticket_flow.escalate_ticket_for_user(
            db,
            user,
            ticket,
            reason=payload.reason,
            target_role=payload.target_role,
            assign_to_user_id=payload.assign_to_user_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if ticket.assigned_to_user_id and ticket.assigned_to_user_id != prev_assignee:
        from app.services import ticket_notify_service as ticket_notify

        ticket_notify.notify_ticket_assigned(
            db,
            ticket,
            assignee_user_id=ticket.assigned_to_user_id,
            actor_user_id=user.id,
        )
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="escalate", entity_type="support_ticket", entity_id=ticket.id, **meta)
    db.commit()
    return ticket_detail_service.get_ticket_detail(db, user, ticket.id)


@router.post("/{ticket_id}/messages", status_code=status.HTTP_201_CREATED)
async def add_message(
    ticket_id: int,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ticket = db.get(SupportTicket, ticket_id)
    if not ticket or not ticket_detail_service._can_view_ticket(db, user, ticket):
        raise HTTPException(status_code=404, detail="Ticket not found")

    content_type = request.headers.get("content-type", "")
    files: List[UploadFile] = []
    is_internal = False
    if "multipart/form-data" in content_type:
        form = await request.form()
        body = str(form.get("body") or "").strip()
        files = att_svc.files_from_form(form)
        raw_internal = str(form.get("is_internal") or "").lower() in ("1", "true", "yes")
        is_internal = raw_internal and (
            user_has_permission(user, "ticket.manage") or user_has_permission(user, "admin.override")
        )
        if is_internal:
            _guard_ticket_staff_write(user, ticket, db)
    else:
        try:
            data = await request.json()
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid JSON body")
        payload_msg = TicketMessageCreate(**data)
        body = payload_msg.body.strip()
        is_internal = payload_msg.is_internal and (
            user_has_permission(user, "ticket.manage") or user_has_permission(user, "admin.override")
        )
        if is_internal:
            _guard_ticket_staff_write(user, ticket, db)

    if not body:
        raise HTTPException(status_code=400, detail="Message body is required")

    msg = TicketMessage(ticket_id=ticket_id, author_user_id=user.id, body=body, is_internal=is_internal)
    db.add(msg)
    db.flush()
    if not is_internal:
        ticket_flow.on_ticket_message(db, user, ticket)
    try:
        await att_svc.save_attachments(db, ticket, user, files, message_id=msg.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="message", entity_type="support_ticket", entity_id=ticket.id, **meta)
    db.commit()
    return ticket_detail_service.get_ticket_detail(db, user, ticket.id)
