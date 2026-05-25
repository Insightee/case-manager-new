from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user, get_request_meta
from app.core.audit import log_audit
from app.core.database import get_db
from app.core.permissions import require_permission
from app.models.case_document import CaseDocument
from app.models.user import User
from app.schemas.case_document import (
    CaseDocumentCommentCreate,
    CaseDocumentCommentRead,
    CaseDocumentCreateJson,
    CaseDocumentDetail,
    CaseDocumentListItem,
    CaseDocumentPatch,
    ParentFeedbackPayload,
    WorkflowPayload,
)
from app.services import case_document_service as doc_svc
from app.storage.local_case_document_storage import case_document_storage

router = APIRouter(tags=["case-documents"])
documents_router = APIRouter(prefix="/documents", tags=["case-documents"])


def _load_doc(db: Session, document_id: int) -> CaseDocument:
    doc = db.scalars(
        select(CaseDocument)
        .where(CaseDocument.id == document_id)
        .options(selectinload(CaseDocument.versions))
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@router.get("/cases/{case_id}/documents", response_model=list[CaseDocumentListItem])
def list_case_documents(
    case_id: int,
    category: Optional[str] = None,
    status: Optional[str] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return doc_svc.list_for_case(db, user, case_id, category=category, status=status)


@router.post("/cases/{case_id}/documents", response_model=CaseDocumentDetail, status_code=201)
async def create_case_document(
    case_id: int,
    request: Request,
    user: User = Depends(require_permission("case_document.create")),
    db: Session = Depends(get_db),
):
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        body = await request.json()
        payload = CaseDocumentCreateJson(**body)
        detail = await doc_svc.create_document(
            db,
            user,
            case_id,
            category=payload.category,
            title=payload.title,
            report_month=payload.report_month,
            report_date=payload.report_date,
            source_type=payload.source_type,
            file=None,
            external_url=payload.external_url,
        )
    else:
        form = await request.form()
        category = form.get("category")
        title = form.get("title")
        source_type = form.get("source_type")
        if not category or not title or not source_type:
            raise HTTPException(status_code=400, detail="category, title, and source_type are required")
        report_month = form.get("report_month")
        report_date_raw = form.get("report_date")
        parsed_date = None
        if report_date_raw:
            from datetime import date as date_type

            parsed_date = date_type.fromisoformat(str(report_date_raw))
        upload = form.get("file")
        file_obj = upload if upload and hasattr(upload, "read") else None
        detail = await doc_svc.create_document(
            db,
            user,
            case_id,
            category=str(category),
            title=str(title),
            report_month=str(report_month) if report_month else None,
            report_date=parsed_date,
            source_type=str(source_type),
            file=file_obj,
            external_url=str(form.get("external_url")) if form.get("external_url") else None,
        )
    meta = get_request_meta(request)
    log_audit(
        db,
        actor_user_id=user.id,
        action="create",
        entity_type="case_document",
        entity_id=detail.id,
        case_id=case_id,
        **meta,
    )
    db.commit()
    return detail


@documents_router.get("/{document_id}", response_model=CaseDocumentDetail)
def get_document(
    document_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    doc = _load_doc(db, document_id)
    doc_svc.require_read(db, user, doc)
    return doc_svc._serialize_detail(db, user, doc)


@documents_router.patch("/{document_id}", response_model=CaseDocumentDetail)
def patch_document(
    document_id: int,
    payload: CaseDocumentPatch,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    doc = _load_doc(db, document_id)
    detail = doc_svc.patch_document(db, user, doc, **payload.model_dump(exclude_unset=True))
    meta = get_request_meta(request)
    log_audit(db, actor_user_id=user.id, action="update", entity_type="case_document", entity_id=doc.id, case_id=doc.case_id, **meta)
    db.commit()
    return detail


@documents_router.post("/{document_id}/versions", response_model=CaseDocumentDetail)
async def add_document_version(
    document_id: int,
    source_type: str = Form(...),
    external_url: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    doc = _load_doc(db, document_id)
    detail = await doc_svc.add_version(
        db, user, doc, source_type=source_type, file=file, external_url=external_url
    )
    db.commit()
    return detail


@documents_router.get("/{document_id}/download")
def download_document(
    document_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    doc = _load_doc(db, document_id)
    info = doc_svc.get_download_info(db, user, doc)
    if info["type"] == "external_link":
        return info
    path, _ = case_document_storage.open_bytes(info["storage_key"])
    return FileResponse(path, filename=info.get("file_name") or "document", media_type=info.get("mime_type"))


@documents_router.get("/{document_id}/comments", response_model=list[CaseDocumentCommentRead])
def list_document_comments(
    document_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    doc = _load_doc(db, document_id)
    return doc_svc.list_comments(db, user, doc)


@documents_router.post("/{document_id}/comments", response_model=CaseDocumentCommentRead, status_code=201)
def create_document_comment(
    document_id: int,
    payload: CaseDocumentCommentCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    doc = _load_doc(db, document_id)
    row = doc_svc.add_comment(db, user, doc, body=payload.body, comment_type=payload.comment_type)
    db.commit()
    return row


@documents_router.post("/{document_id}/workflow/{action}", response_model=CaseDocumentDetail)
def document_workflow(
    document_id: int,
    action: str,
    payload: Optional[WorkflowPayload] = None,
    request: Request = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    doc = _load_doc(db, document_id)
    body = payload or WorkflowPayload()
    detail = doc_svc.run_workflow(
        db,
        user,
        doc,
        action,
        comment=body.comment,
        visibility=body.visibility,
    )
    if request:
        meta = get_request_meta(request)
        log_audit(
            db,
            actor_user_id=user.id,
            action=action,
            entity_type="case_document",
            entity_id=doc.id,
            case_id=doc.case_id,
            new_value=json.dumps({"status": doc.status, "visibility": doc.visibility}),
            **meta,
        )
    db.commit()
    return detail
