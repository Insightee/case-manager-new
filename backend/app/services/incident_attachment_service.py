from __future__ import annotations

from pathlib import Path
from typing import Optional, Sequence

from fastapi import HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.permissions import case_scope_check, user_has_permission
from app.models.incident import Incident
from app.models.incident import IncidentAttachment
from app.models.user import User
from app.services import case_service
from app.storage.object_io import put_stored_bytes, stored_file_response

ALLOWED_MIME_TYPES = frozenset(
    {
        "image/jpeg",
        "image/png",
        "image/webp",
        "image/gif",
        "application/pdf",
        "text/plain",
        "audio/mpeg",
        "audio/mp4",
        "audio/wav",
        "video/mp4",
        "video/quicktime",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }
)

MAX_BYTES = 15 * 1024 * 1024
MAX_FILES = 8


def attachment_to_dict(att: IncidentAttachment) -> dict:
    return {
        "id": att.id,
        "incident_id": att.incident_id,
        "message_id": att.message_id,
        "file_name": att.file_name,
        "mime_type": att.mime_type,
        "size_bytes": att.size_bytes,
        "note": att.note,
        "created_at": att.created_at.isoformat() if att.created_at else None,
    }


def can_access_incident(db: Session, user: User, incident: Incident) -> bool:
    if incident.reported_by_user_id == user.id:
        return True
    if incident.assigned_to_user_id == user.id:
        return True
    if user_has_permission(user, "incident.read_sensitive"):
        if incident.case_id:
            case = case_service.get_case(db, incident.case_id)
            if case and case_scope_check(db, user, case):
                return True
        return True
    return False


async def validate_and_read_files(files: Sequence[UploadFile]) -> list[tuple[str, str, bytes]]:
    if not files:
        return []
    if len(files) > MAX_FILES:
        raise ValueError(f"At most {MAX_FILES} files per upload")
    out: list[tuple[str, str, bytes]] = []
    for f in files:
        if not f.filename:
            raise ValueError("Each file must have a name")
        content_type = (f.content_type or "").split(";")[0].strip().lower()
        if content_type not in ALLOWED_MIME_TYPES:
            raise ValueError(f"File type not allowed: {content_type or 'unknown'}")
        content = await f.read()
        if len(content) > MAX_BYTES:
            raise ValueError("Each file must be 15 MB or less")
        if len(content) == 0:
            raise ValueError("Empty files are not allowed")
        out.append((f.filename, content_type, content))
    return out


async def save_attachments(
    db: Session,
    incident: Incident,
    user: User,
    files: Sequence[UploadFile],
    *,
    note: str | None = None,
    message_id: Optional[int] = None,
) -> list[IncidentAttachment]:
    payloads = await validate_and_read_files(files)
    if not payloads:
        return []
    saved: list[IncidentAttachment] = []
    for filename, mime_type, content in payloads:
        storage_key, _provider = put_stored_bytes(
            "incident-attachments",
            f"incident_{incident.id}",
            filename=filename,
            data=content,
            content_type=mime_type,
        )
        att = IncidentAttachment(
            incident_id=incident.id,
            message_id=message_id,
            file_name=filename,
            file_path=storage_key,
            mime_type=mime_type,
            size_bytes=len(content),
            note=note,
            uploaded_by_user_id=user.id,
        )
        db.add(att)
        saved.append(att)
    db.flush()
    return saved


def list_for_incident(db: Session, incident_id: int) -> list[IncidentAttachment]:
    return list(
        db.scalars(
            select(IncidentAttachment)
            .where(IncidentAttachment.incident_id == incident_id)
            .order_by(IncidentAttachment.created_at.asc())
        ).all()
    )


def get_attachment_or_404(db: Session, attachment_id: int) -> IncidentAttachment:
    att = db.get(IncidentAttachment, attachment_id)
    if not att:
        raise HTTPException(status_code=404, detail="Attachment not found")
    return att


def download_response(attachment: IncidentAttachment):
    return stored_file_response(
        attachment.file_path,
        filename=attachment.file_name,
        media_type=attachment.mime_type,
    )
