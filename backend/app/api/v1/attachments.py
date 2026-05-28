from __future__ import annotations

from typing import Optional

from pathlib import Path
import re

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
from app.storage.object_io import generate_signed_upload_url, object_exists, put_stored_bytes, stored_file_response

router = APIRouter(prefix="/attachments", tags=["attachments"])


class AttachmentUpdate(BaseModel):
    visibility_status: Optional[VisibilityStatus] = None


class SignedUploadRequest(BaseModel):
    case_id: int
    entity_type: str = "iep"
    version: Optional[str] = None
    visibility_status: VisibilityStatus = VisibilityStatus.INTERNAL_ONLY
    file_name: str
    content_type: str = "application/octet-stream"
    file_size: Optional[int] = None


class SignedUploadFinalize(BaseModel):
    upload_token: dict


_SAFE_FILE_NAME = re.compile(r"[^a-zA-Z0-9._-]+")


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
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file not allowed")
    mime = (file.content_type or "application/octet-stream").split(";")[0].strip().lower()
    storage_key, _provider = put_stored_bytes(
        "attachments",
        f"case_{case_id}",
        entity_type or "generic",
        filename=file.filename or "file",
        data=content,
        content_type=mime,
    )
    attachment = Attachment(
        case_id=case_id,
        entity_type=entity_type,
        file_name=file.filename or Path(storage_key).name,
        file_path=storage_key,
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


@router.post("/signed-url")
def create_signed_upload_url(
    payload: SignedUploadRequest,
    user: User = Depends(require_permission("attachment.manage")),
    db: Session = Depends(get_db),
):
    case = case_service.get_case(db, payload.case_id)
    if not case or not case_scope_check(db, user, case):
        raise HTTPException(status_code=404, detail="Case not found")
    safe_name = _SAFE_FILE_NAME.sub("_", (payload.file_name or "file").strip())[:120] or "file"
    key, upload_url = generate_signed_upload_url(
        "attachments",
        f"case_{payload.case_id}",
        payload.entity_type or "generic",
        filename=safe_name,
        content_type=payload.content_type or "application/octet-stream",
        expires_seconds=300,
    )
    token = {
        "case_id": payload.case_id,
        "entity_type": payload.entity_type or "generic",
        "version": payload.version,
        "visibility_status": payload.visibility_status.value,
        "file_name": safe_name,
        "file_path": key,
        "content_type": payload.content_type or "application/octet-stream",
    }
    return {"upload_url": upload_url, "upload_token": token}


@router.post("/signed-url/finalize", status_code=status.HTTP_201_CREATED)
def finalize_signed_upload(
    payload: SignedUploadFinalize,
    request: Request,
    user: User = Depends(require_permission("attachment.manage")),
    db: Session = Depends(get_db),
):
    token = payload.upload_token or {}
    if not isinstance(token, dict):
        raise HTTPException(status_code=400, detail="Invalid upload token")
    case_id = int(token.get("case_id") or 0)
    if case_id <= 0:
        raise HTTPException(status_code=400, detail="Invalid upload token")
    case = case_service.get_case(db, case_id)
    if not case or not case_scope_check(db, user, case):
        raise HTTPException(status_code=404, detail="Case not found")
    file_path = str(token.get("file_path") or "").strip()
    if not file_path:
        raise HTTPException(status_code=400, detail="Invalid upload token")
    if not object_exists(file_path):
        raise HTTPException(status_code=400, detail="Upload not found in storage")

    attachment = Attachment(
        case_id=case_id,
        entity_type=str(token.get("entity_type") or "generic"),
        file_name=str(token.get("file_name") or Path(file_path).name),
        file_path=file_path,
        version=token.get("version"),
        visibility_status=VisibilityStatus(str(token.get("visibility_status") or VisibilityStatus.INTERNAL_ONLY.value)),
        uploaded_by_user_id=user.id,
    )
    db.add(attachment)
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="upload_finalize", entity_type="attachment", entity_id=attachment.id, **meta)
    db.commit()
    db.refresh(attachment)
    return {"id": attachment.id, "file_name": attachment.file_name, "version": attachment.version}


@router.get("/{attachment_id}/download")
def download_attachment(
    attachment_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from sqlalchemy import select

    attachment = db.get(Attachment, attachment_id)
    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")
    case = case_service.get_case(db, attachment.case_id)
    if not case or not case_scope_check(db, user, case):
        raise HTTPException(status_code=404, detail="Attachment not found")
    mime = "text/html" if attachment.file_name.lower().endswith(".html") else "application/octet-stream"
    return stored_file_response(attachment.file_path, filename=attachment.file_name, media_type=mime)


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
