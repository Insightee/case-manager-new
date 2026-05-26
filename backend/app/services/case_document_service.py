from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.audit import log_audit
from app.core.config import settings
from app.core.external_link_validation import validate_external_url
from app.core.permissions import RoleName
from app.models.case_document import (
    CaseDocument,
    CaseDocumentCategory,
    CaseDocumentSourceType,
    CaseDocumentStatus,
    CaseDocumentVersion,
    CaseDocumentVisibility,
    normalize_case_document_status,
)
from app.models.document_comment import CommentType, DocumentComment, DocumentEntityType
from app.models.user import User
from app.schemas.case_document import (
    CaseDocumentCommentRead,
    CaseDocumentDetail,
    CaseDocumentListItem,
    CaseDocumentVersionRead,
)
from app.core.permissions import case_scope_check
from app.services import case_document_access_service as access
from app.services import case_document_workflow_service as workflow
from app.services import case_service, parent_service
from app.storage.local_case_document_storage import (
    ALLOWED_IMAGE_MIME,
    ALLOWED_UPLOAD_MIME,
    MAX_UPLOAD_BYTES,
    case_document_storage,
)


def _valid_category(category: str) -> str:
    raw = (category or "").strip().upper()
    try:
        return CaseDocumentCategory(raw).value
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid category: {category}")


def _version_read(v: CaseDocumentVersion | None) -> CaseDocumentVersionRead | None:
    if not v:
        return None
    return CaseDocumentVersionRead(
        id=v.id,
        version_number=v.version_number,
        source_type=v.source_type,
        file_name=v.file_name,
        mime_type=v.mime_type,
        size_bytes=v.size_bytes,
        external_provider=v.external_provider,
        external_url=v.external_url,
        external_file_id=v.external_file_id,
        created_at=v.created_at,
    )


def _serialize_list_item(db: Session, user: User, doc: CaseDocument, version: CaseDocumentVersion | None) -> CaseDocumentListItem:
    case = case_service.get_case(db, doc.case_id)
    return CaseDocumentListItem(
        id=doc.id,
        case_id=doc.case_id,
        child_id=doc.child_id,
        category=doc.category,
        title=doc.title,
        report_month=doc.report_month,
        report_date=doc.report_date,
        status=normalize_case_document_status(doc.status) or doc.status,
        visibility=doc.visibility,
        submitted_by_user_id=doc.submitted_by_user_id,
        parent_review_status=doc.parent_review_status,
        current_version=_version_read(version),
        allowed_actions=access.allowed_actions(db, user, doc, case),
        created_at=doc.created_at,
        updated_at=doc.updated_at,
    )


def _serialize_detail(db: Session, user: User, doc: CaseDocument) -> CaseDocumentDetail:
    versions = sorted(doc.versions, key=lambda v: v.version_number)
    current = next((v for v in versions if v.id == doc.current_version_id), versions[-1] if versions else None)
    case = case_service.get_case(db, doc.case_id)
    base = _serialize_list_item(db, user, doc, current)
    return CaseDocumentDetail(
        **base.model_dump(),
        parent_feedback=doc.parent_feedback,
        parent_acknowledged_at=doc.parent_acknowledged_at,
        reviewer_user_id=doc.reviewer_user_id,
        versions=[_version_read(v) for v in versions if _version_read(v)],
    )


def get_document_or_404(db: Session, document_id: int) -> CaseDocument:
    doc = db.get(CaseDocument, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


def require_read(db: Session, user: User, doc: CaseDocument) -> None:
    if not access.can_read(db, user, doc):
        raise HTTPException(status_code=404, detail="Document not found")


async def _read_upload(file: UploadFile, *, allow_images: bool) -> tuple[str, str, bytes]:
    if not file.filename:
        raise HTTPException(status_code=400, detail="File must have a name")
    content_type = (file.content_type or "").split(";")[0].strip().lower()
    allowed = set(ALLOWED_UPLOAD_MIME)
    if allow_images:
        allowed |= ALLOWED_IMAGE_MIME
    if content_type not in allowed:
        raise HTTPException(status_code=400, detail="File type not allowed")
    raw = await file.read()
    max_bytes = settings.case_document_max_bytes or MAX_UPLOAD_BYTES
    if len(raw) > max_bytes:
        raise HTTPException(status_code=413, detail="File exceeds 5 MB limit")
    if len(raw) == 0:
        raise HTTPException(status_code=400, detail="Empty file not allowed")
    return file.filename, content_type, raw


def _add_version_upload(
    db: Session,
    doc: CaseDocument,
    user: User,
    *,
    filename: str,
    mime_type: str,
    content: bytes,
) -> CaseDocumentVersion:
    version_number = (max((v.version_number for v in doc.versions), default=0)) + 1
    storage_key = case_document_storage.put(
        case_id=doc.case_id,
        document_id=doc.id,
        version_number=version_number,
        filename=filename,
        content=content,
    )
    version = CaseDocumentVersion(
        case_document_id=doc.id,
        version_number=version_number,
        source_type=CaseDocumentSourceType.UPLOAD.value,
        file_name=filename,
        storage_key=storage_key,
        mime_type=mime_type,
        size_bytes=len(content),
        uploaded_by_user_id=user.id,
    )
    db.add(version)
    db.flush()
    _set_current_version(db, doc, version.id)
    return version


def _set_current_version(db: Session, doc: CaseDocument, version_id: int) -> None:
    doc.current_version_id = version_id
    db.flush()


def _add_version_external(
    db: Session,
    doc: CaseDocument,
    user: User,
    *,
    external_url: str,
) -> CaseDocumentVersion:
    validated = validate_external_url(external_url)
    version_number = (max((v.version_number for v in doc.versions), default=0)) + 1
    version = CaseDocumentVersion(
        case_document_id=doc.id,
        version_number=version_number,
        source_type=CaseDocumentSourceType.EXTERNAL_LINK.value,
        file_name=validated.url[:255],
        external_provider=validated.provider,
        external_url=validated.url,
        external_file_id=validated.external_file_id,
        uploaded_by_user_id=user.id,
    )
    db.add(version)
    db.flush()
    _set_current_version(db, doc, version.id)
    return version


def list_for_case(
    db: Session,
    user: User,
    case_id: int,
    *,
    category: str | None = None,
    status: str | None = None,
) -> list[CaseDocumentListItem]:
    case = case_service.get_case(db, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    if RoleName.PARENT.value in access._role_names(user):
        child_ids = parent_service.child_ids_for_parent(db, user.id)
        if case.child_id not in child_ids:
            raise HTTPException(status_code=404, detail="Case not found")
    elif not access.can_access_clinical_documents(user) or not case_scope_check(db, user, case):
        raise HTTPException(status_code=404, detail="Case not found")

    stmt = select(CaseDocument).where(CaseDocument.case_id == case_id).order_by(CaseDocument.updated_at.desc())
    if category:
        stmt = stmt.where(CaseDocument.category == _valid_category(category))
    if status:
        s = status.strip().upper()
        if s == CaseDocumentStatus.CM_REVIEW.value:
            stmt = stmt.where(CaseDocument.status.in_([CaseDocumentStatus.CM_REVIEW.value, "SUPERVISOR_REVIEW"]))
        else:
            stmt = stmt.where(CaseDocument.status == s)
    docs = list(db.scalars(stmt).all())
    out: list[CaseDocumentListItem] = []
    for doc in docs:
        if not access.can_read(db, user, doc, case):
            continue
        version = db.get(CaseDocumentVersion, doc.current_version_id) if doc.current_version_id else None
        out.append(_serialize_list_item(db, user, doc, version))
    return out


def list_for_parent(db: Session, user_id: int) -> list[dict]:
    case_ids = []
    child_ids = parent_service.child_ids_for_parent(db, user_id)
    if not child_ids:
        return []
    from app.models.case import Case

    case_ids = list(db.scalars(select(Case.id).where(Case.child_id.in_(child_ids))).all())
    if not case_ids:
        return []
    docs = list(
        db.scalars(
            select(CaseDocument)
            .where(CaseDocument.case_id.in_(case_ids))
            .order_by(CaseDocument.updated_at.desc())
        ).all()
    )
    user = db.get(User, user_id)
    items = []
    for doc in docs:
        if not user or not access.parent_can_read_document(doc):
            continue
        case = case_service.get_case(db, doc.case_id)
        version = db.get(CaseDocumentVersion, doc.current_version_id) if doc.current_version_id else None
        row = _serialize_list_item(db, user, doc, version)
        items.append(
            {
                **row.model_dump(),
                "case_code": case.case_code if case else "",
                "child_name": case.child.full_name if case and case.child else "",
            }
        )
    return items


async def create_document(
    db: Session,
    user: User,
    case_id: int,
    *,
    category: str,
    title: str,
    report_month: str | None,
    report_date: date | None,
    source_type: str,
    file: UploadFile | None = None,
    external_url: str | None = None,
) -> CaseDocumentDetail:
    case = case_service.get_case(db, case_id)
    if not case or not access.can_create(db, user, case):
        raise HTTPException(status_code=404, detail="Case not found")
    cat = _valid_category(category)
    title_clean = (title or "").strip()
    if not title_clean:
        raise HTTPException(status_code=400, detail="Title is required")
    doc = CaseDocument(
        case_id=case.id,
        child_id=case.child_id,
        category=cat,
        title=title_clean,
        report_month=report_month,
        report_date=report_date,
        status=CaseDocumentStatus.DRAFT.value,
        visibility=CaseDocumentVisibility.INTERNAL_ONLY.value,
        submitted_by_user_id=user.id,
    )
    db.add(doc)
    db.flush()
    st = (source_type or "").strip().upper()
    allow_images = cat == CaseDocumentCategory.INCIDENT_REPORT.value
    if st == CaseDocumentSourceType.UPLOAD.value:
        if not file:
            raise HTTPException(status_code=400, detail="File is required for upload")
        filename, mime, content = await _read_upload(file, allow_images=allow_images)
        _add_version_upload(db, doc, user, filename=filename, mime_type=mime, content=content)
    elif st == CaseDocumentSourceType.EXTERNAL_LINK.value:
        if not external_url:
            raise HTTPException(status_code=400, detail="external_url is required")
        try:
            _add_version_external(db, doc, user, external_url=external_url)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
    else:
        raise HTTPException(status_code=400, detail="source_type must be UPLOAD or EXTERNAL_LINK")
    db.refresh(doc)
    return _serialize_detail(db, user, doc)


def patch_document(db: Session, user: User, doc: CaseDocument, **fields) -> CaseDocumentDetail:
    require_read(db, user, doc)
    if not access.can_edit_metadata(user, doc):
        raise HTTPException(status_code=403, detail="Cannot edit this document")
    if fields.get("title") is not None:
        doc.title = fields["title"].strip() or doc.title
    if fields.get("category") is not None:
        doc.category = _valid_category(fields["category"])
    if "report_month" in fields:
        doc.report_month = fields["report_month"]
    if "report_date" in fields:
        doc.report_date = fields["report_date"]
    db.flush()
    db.refresh(doc)
    return _serialize_detail(db, user, doc)


async def add_version(
    db: Session,
    user: User,
    doc: CaseDocument,
    *,
    source_type: str,
    file: UploadFile | None = None,
    external_url: str | None = None,
) -> CaseDocumentDetail:
    require_read(db, user, doc)
    if not access.can_edit_metadata(user, doc) and doc.submitted_by_user_id != user.id:
        raise HTTPException(status_code=403, detail="Cannot add version")
    st = (source_type or "").strip().upper()
    allow_images = doc.category == CaseDocumentCategory.INCIDENT_REPORT.value
    if st == CaseDocumentSourceType.UPLOAD.value:
        if not file:
            raise HTTPException(status_code=400, detail="File is required")
        filename, mime, content = await _read_upload(file, allow_images=allow_images)
        _add_version_upload(db, doc, user, filename=filename, mime_type=mime, content=content)
    elif st == CaseDocumentSourceType.EXTERNAL_LINK.value:
        if not external_url:
            raise HTTPException(status_code=400, detail="external_url is required")
        try:
            _add_version_external(db, doc, user, external_url=external_url)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
    else:
        raise HTTPException(status_code=400, detail="Invalid source_type")
    db.refresh(doc)
    return _serialize_detail(db, user, doc)


def list_comments(db: Session, user: User, doc: CaseDocument) -> list[CaseDocumentCommentRead]:
    require_read(db, user, doc)
    rows = list(
        db.scalars(
            select(DocumentComment)
            .where(
                DocumentComment.entity_type == DocumentEntityType.CASE_DOCUMENT.value,
                DocumentComment.entity_id == doc.id,
            )
            .order_by(DocumentComment.created_at.asc())
        ).all()
    )
    return [
        CaseDocumentCommentRead(
            id=c.id,
            author_user_id=c.author_user_id,
            comment_type=c.comment_type,
            body=c.body,
            created_at=c.created_at,
        )
        for c in rows
    ]


def add_comment(
    db: Session,
    user: User,
    doc: CaseDocument,
    *,
    body: str,
    comment_type: str = "GENERAL",
) -> CaseDocumentCommentRead:
    require_read(db, user, doc)
    if "comment" not in access.allowed_actions(db, user, doc):
        raise HTTPException(status_code=403, detail="Cannot comment on this document")
    text = (body or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Comment body is required")
    ct = comment_type if comment_type in {e.value for e in CommentType} else CommentType.GENERAL.value
    row = DocumentComment(
        entity_type=DocumentEntityType.CASE_DOCUMENT.value,
        entity_id=doc.id,
        case_id=doc.case_id,
        author_user_id=user.id,
        comment_type=ct,
        body=text,
    )
    db.add(row)
    db.flush()
    return CaseDocumentCommentRead(
        id=row.id,
        author_user_id=row.author_user_id,
        comment_type=row.comment_type,
        body=row.body,
        created_at=row.created_at,
    )


def run_workflow(
    db: Session,
    user: User,
    doc: CaseDocument,
    action: str,
    *,
    comment: str | None = None,
    visibility: str | None = None,
) -> CaseDocumentDetail:
    require_read(db, user, doc)
    action = action.strip().lower()
    try:
        if action == "submit":
            workflow.submit(db, user, doc, comment)
        elif action == "approve":
            workflow.approve(db, user, doc, comment=comment, visibility=visibility)
        elif action == "request_changes":
            workflow.request_changes(db, user, doc, comment=comment)
        elif action == "publish_client":
            workflow.publish_client(db, user, doc, comment)
        elif action == "archive":
            workflow.archive(db, user, doc, comment)
        elif action == "parent_approve":
            workflow.parent_approve(db, user, doc)
        elif action == "parent_feedback":
            if not comment:
                raise HTTPException(status_code=400, detail="message is required")
            workflow.parent_feedback(db, user, doc, comment)
        else:
            raise HTTPException(status_code=400, detail=f"Unknown action: {action}")
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    db.refresh(doc)
    return _serialize_detail(db, user, doc)


def get_download_info(db: Session, user: User, doc: CaseDocument) -> dict:
    require_read(db, user, doc)
    version = db.get(CaseDocumentVersion, doc.current_version_id) if doc.current_version_id else None
    if not version:
        raise HTTPException(status_code=404, detail="No document version")
    if version.source_type == CaseDocumentSourceType.EXTERNAL_LINK.value:
        return {
            "type": "external_link",
            "external_url": version.external_url,
            "external_provider": version.external_provider,
            "warning": "Access depends on Google sharing settings.",
        }
    if not version.storage_key:
        raise HTTPException(status_code=404, detail="File not found")
    return {
        "type": "upload",
        "storage_key": version.storage_key,
        "file_name": version.file_name,
        "mime_type": version.mime_type,
    }
