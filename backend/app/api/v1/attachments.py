from __future__ import annotations

from typing import Optional

import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_request_meta
from app.core.audit import log_audit
from app.core.database import get_db
from app.core.permissions import case_scope_check, require_permission
from app.models.attachment import Attachment
from app.models.user import User
from app.models.visibility import VisibilityStatus
from app.services import case_service

router = APIRouter(prefix="/attachments", tags=["attachments"])
UPLOAD_DIR = Path("uploads")


class AttachmentUpdate(BaseModel):
    visibility_status: Optional[VisibilityStatus] = None


@router.post("", status_code=status.HTTP_201_CREATED)
async def upload_attachment(
    case_id: int = Form(...),
    entity_type: str = Form("iep"),
    version: Optional[str] = Form(None),
    visibility_status: VisibilityStatus = Form(VisibilityStatus.INTERNAL_ONLY),
    file: UploadFile = File(...),
    request: Request = None,
    user: User = Depends(require_permission("attachment.manage")),
    db: Session = Depends(get_db),
):
    case = case_service.get_case(db, case_id)
    if not case or not case_scope_check(db, user, case):
        raise HTTPException(status_code=404, detail="Case not found")
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    ext = Path(file.filename or "file").suffix
    stored_name = f"{uuid.uuid4()}{ext}"
    path = UPLOAD_DIR / stored_name
    content = await file.read()
    path.write_bytes(content)
    attachment = Attachment(
        case_id=case_id,
        entity_type=entity_type,
        file_name=file.filename or stored_name,
        file_path=str(path),
        version=version,
        visibility_status=visibility_status,
        uploaded_by_user_id=user.id,
    )
    db.add(attachment)
    meta = get_request_meta(request) if request else {}
    log_audit(db, actor_user_id=user.id, action="upload", entity_type="attachment", entity_id=attachment.id, **meta)
    db.commit()
    db.refresh(attachment)
    return {"id": attachment.id, "file_name": attachment.file_name, "version": attachment.version}


@router.get("/{attachment_id}/download")
def download_attachment(
    attachment_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from fastapi.responses import FileResponse
    from sqlalchemy import select

    attachment = db.get(Attachment, attachment_id)
    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")
    case = case_service.get_case(db, attachment.case_id)
    if not case or not case_scope_check(db, user, case):
        raise HTTPException(status_code=404, detail="Attachment not found")
    path = Path(attachment.file_path)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="File not found on disk")
    return FileResponse(path, filename=attachment.file_name)


@router.patch("/{attachment_id}")
def update_attachment(
    attachment_id: int,
    payload: AttachmentUpdate,
    request: Request,
    user: User = Depends(require_permission("attachment.manage")),
    db: Session = Depends(get_db),
):
    attachment = db.get(Attachment, attachment_id)
    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")
    case = case_service.get_case(db, attachment.case_id)
    if not case or not case_scope_check(db, user, case):
        raise HTTPException(status_code=404, detail="Attachment not found")
    if payload.visibility_status is not None:
        attachment.visibility_status = payload.visibility_status
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="update", entity_type="attachment", entity_id=attachment.id, **meta)
    db.commit()
    return {
        "id": attachment.id,
        "visibility_status": attachment.visibility_status.value,
    }


@router.get("")
def list_attachments(case_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    case = case_service.get_case(db, case_id)
    if not case or not case_scope_check(db, user, case):
        raise HTTPException(status_code=404, detail="Case not found")
    from sqlalchemy import select

    rows = db.scalars(select(Attachment).where(Attachment.case_id == case_id)).all()
    return [{"id": a.id, "file_name": a.file_name, "version": a.version, "visibility_status": a.visibility_status.value} for a in rows]
