from __future__ import annotations

from pathlib import Path
from typing import Optional, Sequence

from fastapi import HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.permissions import case_scope_check, user_has_permission
from app.models.support_ticket import SupportTicket
from app.models.ticket_attachment import TicketAttachment
from app.models.user import User
from app.services import case_service
from app.storage.object_io import put_stored_bytes, stored_file_response

def files_from_form(form) -> list[UploadFile]:
    out: list[UploadFile] = []
    for _key, value in form.multi_items():
        if hasattr(value, "read") and getattr(value, "filename", None):
            out.append(value)
    return out


ALLOWED_MIME_TYPES = frozenset(
    {
        "image/jpeg",
        "image/png",
        "image/webp",
        "application/pdf",
        "text/plain",
    }
)


def attachment_to_dict(att: TicketAttachment) -> dict:
    return {
        "id": att.id,
        "ticket_id": att.ticket_id,
        "message_id": att.message_id,
        "file_name": att.file_name,
        "mime_type": att.mime_type,
        "size_bytes": att.size_bytes,
        "created_at": att.created_at.isoformat() if att.created_at else None,
    }


def count_for_ticket(db: Session, ticket_id: int) -> int:
    return int(
        db.scalar(select(func.count()).select_from(TicketAttachment).where(TicketAttachment.ticket_id == ticket_id))
        or 0
    )


def list_for_ticket(db: Session, ticket_id: int) -> list[TicketAttachment]:
    return list(
        db.scalars(
            select(TicketAttachment)
            .where(TicketAttachment.ticket_id == ticket_id)
            .order_by(TicketAttachment.created_at.asc())
        ).all()
    )


def can_access_ticket(db: Session, user: User, ticket: SupportTicket) -> bool:
    if ticket.raised_by_user_id == user.id:
        return True
    if ticket.assigned_to_user_id == user.id:
        return True
    if user_has_permission(user, "ticket.manage") or user_has_permission(user, "admin.override"):
        if ticket.case_id:
            case = case_service.get_case(db, ticket.case_id)
            if case and case_scope_check(db, user, case):
                return True
        return True
    if ticket.case_id:
        case = case_service.get_case(db, ticket.case_id)
        return bool(case and case_scope_check(db, user, case))
    return False


def can_access_attachment(db: Session, user: User, attachment: TicketAttachment) -> bool:
    ticket = attachment.ticket or db.get(SupportTicket, attachment.ticket_id)
    if not ticket:
        return False
    return can_access_ticket(db, user, ticket)


async def validate_and_read_files(files: Sequence[UploadFile]) -> list[tuple[str, str, bytes]]:
    if not files:
        return []
    if len(files) > settings.ticket_attachment_max_files:
        raise ValueError(f"At most {settings.ticket_attachment_max_files} files per upload")
    out: list[tuple[str, str, bytes]] = []
    for f in files:
        if not f.filename:
            raise ValueError("Each file must have a name")
        content_type = (f.content_type or "").split(";")[0].strip().lower()
        if content_type not in ALLOWED_MIME_TYPES:
            raise ValueError(f"File type not allowed: {content_type or 'unknown'}")
        content = await f.read()
        if len(content) > settings.ticket_attachment_max_bytes:
            raise ValueError(f"Each file must be {settings.ticket_attachment_max_bytes // (1024 * 1024)} MB or less")
        if len(content) == 0:
            raise ValueError("Empty files are not allowed")
        out.append((f.filename, content_type, content))
    return out


async def save_attachments(
    db: Session,
    ticket: SupportTicket,
    user: User,
    files: Sequence[UploadFile],
    *,
    message_id: Optional[int] = None,
) -> list[TicketAttachment]:
    payloads = await validate_and_read_files(files)
    if not payloads:
        return []
    saved: list[TicketAttachment] = []
    for filename, mime_type, content in payloads:
        storage_key, _provider = put_stored_bytes(
            "ticket-attachments",
            f"ticket_{ticket.id}",
            filename=filename,
            data=content,
            content_type=mime_type,
        )
        att = TicketAttachment(
            ticket_id=ticket.id,
            message_id=message_id,
            file_name=filename,
            file_path=storage_key,
            mime_type=mime_type,
            size_bytes=len(content),
            uploaded_by_user_id=user.id,
        )
        db.add(att)
        saved.append(att)
    db.flush()
    return saved


def download_response(attachment: TicketAttachment):
    return stored_file_response(
        attachment.file_path,
        filename=attachment.file_name,
        media_type=attachment.mime_type,
    )


def get_attachment_or_404(db: Session, attachment_id: int) -> TicketAttachment:
    att = db.get(TicketAttachment, attachment_id)
    if not att:
        raise HTTPException(status_code=404, detail="Attachment not found")
    return att
