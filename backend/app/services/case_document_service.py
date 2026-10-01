from __future__ import annotations

from datetime import date, time
from typing import Optional

from fastapi import HTTPException, UploadFile
from sqlalchemy import and_, or_, select
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
    normalize_case_document_visibility,
    visibility_rank,
    normalize_case_document_status,
)
from app.models.case_manager_meeting import CaseManagerMeeting, MeetingStatus
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
from app.services.mentor_scope_service import is_mentor_only_on_case
from app.storage.local_case_document_storage import (
    ALLOWED_IMAGE_MIME,
    ALLOWED_UPLOAD_MIME,
    MAX_UPLOAD_BYTES,
    case_document_storage,
)
from app.storage.object_io import get_storage_backend


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


def _serialize_list_item(
    db: Session,
    user: User,
    doc: CaseDocument,
    version: CaseDocumentVersion | None,
    *,
    meeting_context: dict[int, tuple[str, str | None, str | None, str | None]] | None = None,
) -> CaseDocumentListItem:
    case = case_service.get_case(db, doc.case_id)
    row = CaseDocumentListItem(
        id=doc.id,
        case_id=doc.case_id,
        meeting_id=doc.meeting_id,
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
    if doc.meeting_id and meeting_context:
        meeting_series_id, scheduled_date, scheduled_time, meeting_title, meeting_status = meeting_context.get(
            doc.meeting_id, (None, None, None, None, None)
        )
        row.meeting_series_id = meeting_series_id
        row.meeting_scheduled_date = scheduled_date
        row.meeting_scheduled_time = scheduled_time
        row.meeting_title = meeting_title
        row.meeting_status = meeting_status
    return row


def _serialize_detail(db: Session, user: User, doc: CaseDocument) -> CaseDocumentDetail:
    versions = sorted(doc.versions, key=lambda v: v.version_number)
    current = next((v for v in versions if v.id == doc.current_version_id), versions[-1] if versions else None)
    case = case_service.get_case(db, doc.case_id)
    meeting_context = _meeting_document_context(db, doc.case_id) if case else {}
    base = _serialize_list_item(db, user, doc, current, meeting_context=meeting_context)
    return CaseDocumentDetail(
        **base.model_dump(),
        parent_feedback=doc.parent_feedback,
        parent_acknowledged_at=doc.parent_acknowledged_at,
        reviewer_user_id=doc.reviewer_user_id,
        versions=[_version_read(v) for v in versions if _version_read(v)],
    )


def _current_version(doc: CaseDocument) -> CaseDocumentVersion | None:
    if not doc.current_version_id:
        return None
    return next((v for v in doc.versions if v.id == doc.current_version_id), None)


def _meeting_title(meeting: CaseManagerMeeting) -> str:
    return f"Meeting notes — {meeting.scheduled_date.strftime('%d-%m-%Y')}"


def _meeting_attachment_title(meeting: CaseManagerMeeting) -> str:
    return f"Meeting file — {meeting.scheduled_date.strftime('%d-%m-%Y')}"


def _meeting_series_meetings(db: Session, case_id: int) -> list[CaseManagerMeeting]:
    return list(
        db.scalars(
            select(CaseManagerMeeting)
            .where(CaseManagerMeeting.case_id == case_id)
            .order_by(
                CaseManagerMeeting.scheduled_date.desc(),
                CaseManagerMeeting.scheduled_time.desc(),
                CaseManagerMeeting.id.desc(),
            )
        ).all()
    )


def _series_meeting_map(meetings: list[CaseManagerMeeting]) -> dict[str, CaseManagerMeeting]:
    grouped: dict[str, list[CaseManagerMeeting]] = {}
    for meeting in meetings:
        grouped.setdefault(meeting.series_id, []).append(meeting)
    out: dict[str, CaseManagerMeeting] = {}
    for series_id, rows in grouped.items():
        active = [row for row in rows if row.status != MeetingStatus.RESCHEDULED]
        ordered = active or rows
        out[series_id] = sorted(
            ordered,
            key=lambda row: (
                row.scheduled_date,
                row.scheduled_time or time.min,
                row.id,
            ),
        )[-1]
    return out


def _meeting_document_context(
    db: Session,
    case_id: int,
) -> dict[int, tuple[str, date | None, str | None, str | None, str | None]]:
    meetings = _meeting_series_meetings(db, case_id)
    if not meetings:
        return {}
    series_meetings = _series_meeting_map(meetings)
    context: dict[int, tuple[str, date | None, str | None, str | None, str | None]] = {}
    for meeting in meetings:
        series_meeting = series_meetings.get(meeting.series_id, meeting)
        context[meeting.id] = (
            meeting.series_id,
            series_meeting.scheduled_date,
            series_meeting.scheduled_time.strftime("%H:%M") if series_meeting.scheduled_time else None,
            series_meeting.title or series_meeting.meeting_type.value,
            series_meeting.status.value if series_meeting.status else None,
        )
    return context


def _write_document_text_version(
    db: Session,
    doc: CaseDocument,
    user: User,
    *,
    file_name: str,
    content: bytes,
) -> None:
    version = _current_version(doc)
    if version and version.storage_key:
        backend = get_storage_backend()
        backend.put_bytes(version.storage_key, content, "text/plain")
        version.file_name = file_name
        version.mime_type = "text/plain"
        version.size_bytes = len(content)
        version.source_type = CaseDocumentSourceType.UPLOAD.value
        version.uploaded_by_user_id = user.id
        return
    version_number = (max((v.version_number for v in doc.versions), default=0)) + 1
    storage_key = case_document_storage.put(
        case_id=doc.case_id,
        document_id=doc.id,
        version_number=version_number,
        filename=file_name,
        content=content,
        content_type="text/plain",
    )
    version = CaseDocumentVersion(
        case_document_id=doc.id,
        version_number=version_number,
        source_type=CaseDocumentSourceType.UPLOAD.value,
        file_name=file_name,
        storage_key=storage_key,
        mime_type="text/plain",
        size_bytes=len(content),
        uploaded_by_user_id=user.id,
    )
    db.add(version)
    db.flush()
    doc.current_version_id = version.id


def _find_meeting_document(
    db: Session,
    meeting: CaseManagerMeeting,
    *,
    title_prefix: str,
) -> CaseDocument | None:
    meeting_ids = list(
        db.scalars(
            select(CaseManagerMeeting.id).where(CaseManagerMeeting.series_id == meeting.series_id)
        ).all()
    )
    if not meeting_ids:
        return None
    return db.scalars(
        select(CaseDocument).where(
            CaseDocument.case_id == meeting.case_id,
            CaseDocument.meeting_id.in_(meeting_ids),
            CaseDocument.category == CaseDocumentCategory.CASE_MANAGER_MEETING_REPORT.value,
            CaseDocument.title.ilike(f"{title_prefix}%"),
        )
        .order_by(CaseDocument.updated_at.desc(), CaseDocument.id.desc())
    ).first()


def _serialize_meeting_doc(
    db: Session,
    user: User,
    doc: CaseDocument,
    *,
    meeting_context: dict[int, tuple[str, date | None, str | None, str | None, str | None]] | None = None,
) -> CaseDocumentListItem:
    base = _serialize_list_item(db, user, doc, db.get(CaseDocumentVersion, doc.current_version_id) if doc.current_version_id else None)
    if doc.meeting_id and meeting_context:
        meeting_series_id, scheduled_date, scheduled_time, meeting_title, meeting_status = meeting_context.get(
            doc.meeting_id, (None, None, None, None, None)
        )
        return base.model_copy(
            update={
                "meeting_id": doc.meeting_id,
                "meeting_series_id": meeting_series_id,
                "meeting_scheduled_date": scheduled_date,
                "meeting_scheduled_time": scheduled_time,
                "meeting_title": meeting_title,
                "meeting_status": meeting_status,
            }
        )
    return base.model_copy(update={"meeting_id": doc.meeting_id})


def upsert_meeting_notes_document(
    db: Session,
    user: User,
    meeting: CaseManagerMeeting,
    *,
    notes_summary: str,
) -> CaseDocumentDetail | None:
    if not meeting.case_id:
        return None
    title = _meeting_title(meeting)
    cleaned = (notes_summary or "").strip()
    if not cleaned:
        return None
    doc = _find_meeting_document(db, meeting, title_prefix="Meeting notes —")
    if not doc:
        case = case_service.get_case(db, meeting.case_id)
        if not case:
            raise HTTPException(status_code=404, detail="Case not found")
        doc = CaseDocument(
            case_id=case.id,
            meeting_id=meeting.id,
            child_id=case.child_id,
            category=CaseDocumentCategory.CASE_MANAGER_MEETING_REPORT.value,
            title=title,
            report_date=meeting.scheduled_date,
            status=CaseDocumentStatus.DRAFT.value,
            visibility=CaseDocumentVisibility.INTERNAL.value,
            submitted_by_user_id=user.id,
        )
        db.add(doc)
        db.flush()
    else:
        doc.meeting_id = meeting.id
        doc.title = title
        doc.report_date = meeting.scheduled_date
        doc.visibility = CaseDocumentVisibility.INTERNAL.value
    _write_document_text_version(
        db,
        doc,
        user,
        file_name=f"{title}.txt",
        content=cleaned.encode("utf-8"),
    )
    db.flush()
    db.refresh(doc)
    return _serialize_detail(db, user, doc)


async def create_meeting_attachment_document(
    db: Session,
    user: User,
    meeting: CaseManagerMeeting,
    *,
    file: UploadFile,
) -> CaseDocumentDetail:
    if not meeting.case_id:
        raise HTTPException(status_code=400, detail="File uploads require a case-linked meeting")
    case = case_service.get_case(db, meeting.case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    filename, mime, content = await _read_upload(file, allow_images=False)
    doc = CaseDocument(
        case_id=case.id,
        meeting_id=meeting.id,
        child_id=case.child_id,
        category=CaseDocumentCategory.CASE_MANAGER_MEETING_REPORT.value,
        title=_meeting_attachment_title(meeting),
        report_date=meeting.scheduled_date,
        status=CaseDocumentStatus.DRAFT.value,
        visibility=CaseDocumentVisibility.INTERNAL.value,
        submitted_by_user_id=user.id,
    )
    db.add(doc)
    db.flush()
    _add_version_upload(db, doc, user, filename=filename, mime_type=mime, content=content)
    db.refresh(doc)
    return _serialize_detail(db, user, doc)


def list_for_meeting_series(db: Session, user: User, meeting_id: int) -> list[CaseDocumentListItem]:
    meeting = db.get(CaseManagerMeeting, meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    if not meeting.case_id:
        return []
    context = _meeting_document_context(db, meeting.case_id)
    meeting_ids = list(
        db.scalars(
            select(CaseManagerMeeting.id).where(CaseManagerMeeting.series_id == meeting.series_id)
        ).all()
    )
    if not meeting_ids:
        return []
    docs = list(
        db.scalars(
            select(CaseDocument)
            .where(
                CaseDocument.case_id == meeting.case_id,
                CaseDocument.meeting_id.in_(meeting_ids),
            )
            .order_by(CaseDocument.updated_at.desc())
        ).all()
    )
    out: list[CaseDocumentListItem] = []
    for doc in docs:
        if not access.can_read(db, user, doc):
            continue
        out.append(_serialize_meeting_doc(db, user, doc, meeting_context=context))
    return out


def _comment_visibility_for_user(user: User) -> str:
    return "parent_team" if RoleName.PARENT.value in access._role_names(user) else "internal_only"


def _visibility_storage_value(target_visibility: str | None) -> str | None:
    normalized = normalize_case_document_visibility(target_visibility)
    if normalized == CaseDocumentVisibility.INTERNAL.value:
        return CaseDocumentVisibility.INTERNAL_ONLY.value
    if normalized == CaseDocumentVisibility.CARE_TEAM.value:
        return CaseDocumentVisibility.CLIENT_VISIBLE_AFTER_APPROVAL.value
    if normalized == CaseDocumentVisibility.CLIENT.value:
        return CaseDocumentVisibility.CLIENT_VISIBLE.value
    return target_visibility


def _validate_visibility_change(doc: CaseDocument, target_visibility: str | None) -> None:
    if target_visibility is None:
        return
    version = _current_version(doc)
    if version and version.source_type == CaseDocumentSourceType.EXTERNAL_LINK.value:
        if visibility_rank(target_visibility) > visibility_rank(CaseDocumentVisibility.INTERNAL.value):
            raise HTTPException(status_code=400, detail="External links cannot be shared beyond internal-only")


def _can_parent_read_comment(comment: DocumentComment) -> bool:
    return comment.visibility == "parent_team"


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
        content_type=mime_type,
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
    meeting_context = _meeting_document_context(db, case_id)
    roles = access._role_names(user)
    if category:
        stmt = stmt.where(CaseDocument.category == _valid_category(category))
    if status:
        s = status.strip().upper()
        if s == CaseDocumentStatus.CM_REVIEW.value:
            stmt = stmt.where(CaseDocument.status.in_([CaseDocumentStatus.CM_REVIEW.value, "SUPERVISOR_REVIEW"]))
        else:
            stmt = stmt.where(CaseDocument.status == s)
    if RoleName.PARENT.value in roles:
        stmt = stmt.where(
            or_(
                and_(
                    CaseDocument.visibility.in_(
                        [
                            CaseDocumentVisibility.CLIENT_VISIBLE.value,
                            CaseDocumentVisibility.CLIENT.value,
                        ]
                    ),
                    CaseDocument.status.in_(
                        [
                            CaseDocumentStatus.CLIENT_REVIEW.value,
                            CaseDocumentStatus.APPROVED.value,
                        ]
                    ),
                )
            )
        )
    elif RoleName.THERAPIST.value in roles and RoleName.CASE_MANAGER.value not in roles:
        stmt = stmt.where(
            or_(
                and_(
                    CaseDocument.status.in_(
                        [
                            CaseDocumentStatus.DRAFT.value,
                            CaseDocumentStatus.CHANGES_REQUESTED.value,
                        ]
                    ),
                    CaseDocument.submitted_by_user_id == user.id,
                ),
                CaseDocument.visibility.in_(
                    [
                        CaseDocumentVisibility.CLIENT_VISIBLE_AFTER_APPROVAL.value,
                        CaseDocumentVisibility.CLIENT_VISIBLE.value,
                        CaseDocumentVisibility.CARE_TEAM.value,
                        CaseDocumentVisibility.CLIENT.value,
                    ]
                ),
            )
        )
    docs = list(db.scalars(stmt).all())
    out: list[CaseDocumentListItem] = []
    for doc in docs:
        if not access.can_read(db, user, doc, case):
            continue
        version = db.get(CaseDocumentVersion, doc.current_version_id) if doc.current_version_id else None
        out.append(_serialize_list_item(db, user, doc, version, meeting_context=meeting_context))
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
    meeting_context: dict[int, tuple[str, date | None, str | None, str | None, str | None]] = {}
    for doc in docs:
        if not user or not access.parent_can_read_document(doc):
            continue
        case = case_service.get_case(db, doc.case_id)
        version = db.get(CaseDocumentVersion, doc.current_version_id) if doc.current_version_id else None
        if not meeting_context and case:
            meeting_context = _meeting_document_context(db, doc.case_id)
        row = _serialize_list_item(db, user, doc, version, meeting_context=meeting_context)
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
    share_with_cm: bool = False,
    share_with_parents: bool = False,
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

    if st == CaseDocumentSourceType.EXTERNAL_LINK.value and share_with_parents:
        raise HTTPException(status_code=400, detail="External links cannot be shared beyond internal-only")

    if share_with_parents:
        doc.visibility = CaseDocumentVisibility.CLIENT_VISIBLE_AFTER_APPROVAL.value

    if share_with_cm:
        workflow.submit(db, user, doc)

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
    parent_view = RoleName.PARENT.value in access._role_names(user)
    rows = list(
        db.scalars(
            select(DocumentComment)
            .where(
                DocumentComment.entity_type == DocumentEntityType.CASE_DOCUMENT.value,
                DocumentComment.entity_id == doc.id,
                *(
                    [DocumentComment.visibility == "parent_team"]
                    if parent_view
                    else []
                ),
            )
            .order_by(DocumentComment.created_at.asc())
        ).all()
    )
    if parent_view:
        rows = [row for row in rows if _can_parent_read_comment(row)]
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
    parent_view = RoleName.PARENT.value in access._role_names(user)
    row = DocumentComment(
        entity_type=DocumentEntityType.CASE_DOCUMENT.value,
        entity_id=doc.id,
        case_id=doc.case_id,
        author_user_id=user.id,
        comment_type=ct,
        visibility="parent_team" if parent_view else "internal_only",
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


def set_visibility(
    db: Session,
    user: User,
    doc: CaseDocument,
    *,
    target_visibility: str,
    reason: str,
) -> CaseDocumentDetail:
    require_read(db, user, doc)
    case = case_service.get_case(db, doc.case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    if is_mentor_only_on_case(db, user, case):
        raise HTTPException(status_code=403, detail="Cannot update visibility from mentor scope")
    target = (target_visibility or "").strip()
    if not target:
        raise HTTPException(status_code=400, detail="target visibility is required")
    if not reason or not reason.strip():
        raise HTTPException(status_code=400, detail="reason is required")
    _validate_visibility_change(doc, target)
    if target == doc.visibility:
        return _serialize_detail(db, user, doc)
    doc.visibility = _visibility_storage_value(target) or doc.visibility
    db.flush()
    db.refresh(doc)
    return _serialize_detail(db, user, doc)


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
