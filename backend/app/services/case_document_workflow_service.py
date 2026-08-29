from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.case_document import (
    CaseDocument,
    CaseDocumentParentReviewStatus,
    CaseDocumentStatus,
    CaseDocumentVisibility,
    CaseDocumentWorkflowEvent,
    normalize_case_document_visibility,
    visibility_rank,
    normalize_case_document_status,
    statuses_awaiting_cm_review,
)
from app.models.user import User
from app.services import case_document_access_service as access


def _record(
    db: Session,
    doc: CaseDocument,
    *,
    action: str,
    actor_user_id: int,
    from_status: str | None,
    to_status: str | None,
    comment: str | None = None,
) -> None:
    db.add(
        CaseDocumentWorkflowEvent(
            case_document_id=doc.id,
            action=action,
            from_status=from_status,
            to_status=to_status,
            actor_user_id=actor_user_id,
            comment=comment,
        )
    )


def _current_version(doc: CaseDocument):
    return next((v for v in doc.versions if v.id == doc.current_version_id), None)


def _storage_visibility_value(target_visibility: str | None) -> str | None:
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
    current_version = _current_version(doc)
    if current_version and current_version.source_type == "EXTERNAL_LINK":
        if visibility_rank(target_visibility) > visibility_rank(CaseDocumentVisibility.INTERNAL.value):
            raise ValueError("External links cannot be shared beyond internal-only")


def submit(db: Session, user: User, doc: CaseDocument, comment: str | None = None) -> CaseDocument:
    if doc.submitted_by_user_id != user.id and not access.can_review(db, user, doc):
        raise PermissionError("Cannot submit this document")
    if doc.status not in (
        CaseDocumentStatus.DRAFT.value,
        CaseDocumentStatus.CHANGES_REQUESTED.value,
    ):
        raise ValueError("Document cannot be submitted in its current state")
    if not doc.current_version_id:
        raise ValueError("Add a file or link before submitting")
    old = doc.status
    doc.status = CaseDocumentStatus.CM_REVIEW.value
    _record(db, doc, action="submit", actor_user_id=user.id, from_status=old, to_status=doc.status, comment=comment)
    db.flush()
    return doc


def approve(
    db: Session,
    user: User,
    doc: CaseDocument,
    *,
    comment: str | None = None,
    visibility: str | None = None,
) -> CaseDocument:
    if not access.can_review(db, user, doc):
        raise PermissionError("Cannot approve this document")
    if normalize_case_document_status(doc.status) not in statuses_awaiting_cm_review():
        raise ValueError("Document is not awaiting review")
    old = doc.status
    doc.status = CaseDocumentStatus.APPROVED.value
    doc.reviewer_user_id = user.id
    target_visibility = visibility or (
        CaseDocumentVisibility.INTERNAL_ONLY.value
        if (_current_version(doc) and _current_version(doc).source_type == "EXTERNAL_LINK")
        else CaseDocumentVisibility.CLIENT_VISIBLE_AFTER_APPROVAL.value
    )
    _validate_visibility_change(doc, target_visibility)
    doc.visibility = _storage_visibility_value(target_visibility) or doc.visibility
    _record(db, doc, action="approve", actor_user_id=user.id, from_status=old, to_status=doc.status, comment=comment)
    db.flush()
    return doc


def request_changes(
    db: Session,
    user: User,
    doc: CaseDocument,
    *,
    comment: str | None = None,
) -> CaseDocument:
    if not access.can_review(db, user, doc):
        raise PermissionError("Cannot request changes")
    if normalize_case_document_status(doc.status) not in statuses_awaiting_cm_review():
        raise ValueError("Document is not under review")
    old = doc.status
    doc.status = CaseDocumentStatus.CHANGES_REQUESTED.value
    doc.reviewer_user_id = user.id
    _record(
        db,
        doc,
        action="request_changes",
        actor_user_id=user.id,
        from_status=old,
        to_status=doc.status,
        comment=comment,
    )
    db.flush()
    return doc


def publish_client(db: Session, user: User, doc: CaseDocument, comment: str | None = None) -> CaseDocument:
    if not access.can_review(db, user, doc):
        raise PermissionError("Cannot publish to client")
    if doc.status != CaseDocumentStatus.APPROVED.value:
        raise ValueError("Document must be approved first")
    _validate_visibility_change(doc, CaseDocumentVisibility.CLIENT.value)
    old = doc.status
    doc.status = CaseDocumentStatus.CLIENT_REVIEW.value
    doc.visibility = CaseDocumentVisibility.CLIENT_VISIBLE.value
    doc.parent_review_status = CaseDocumentParentReviewStatus.PENDING.value
    doc.parent_feedback = None
    _record(
        db,
        doc,
        action="publish_client",
        actor_user_id=user.id,
        from_status=old,
        to_status=doc.status,
        comment=comment,
    )
    db.flush()
    return doc


def archive(db: Session, user: User, doc: CaseDocument, comment: str | None = None) -> CaseDocument:
    if not access.can_review(db, user, doc):
        raise PermissionError("Cannot archive")
    old = doc.status
    doc.status = CaseDocumentStatus.ARCHIVED.value
    _record(db, doc, action="archive", actor_user_id=user.id, from_status=old, to_status=doc.status, comment=comment)
    db.flush()
    return doc


def parent_approve(db: Session, user: User, doc: CaseDocument) -> CaseDocument:
    if doc.status != CaseDocumentStatus.CLIENT_REVIEW.value:
        raise ValueError("Document is not awaiting client review")
    old = doc.status
    doc.parent_review_status = CaseDocumentParentReviewStatus.APPROVED.value
    doc.parent_acknowledged_at = datetime.now(timezone.utc)
    doc.status = CaseDocumentStatus.APPROVED.value
    _record(
        db,
        doc,
        action="parent_approve",
        actor_user_id=user.id,
        from_status=old,
        to_status=doc.status,
    )
    db.flush()
    return doc


def parent_feedback(db: Session, user: User, doc: CaseDocument, message: str) -> CaseDocument:
    if doc.status != CaseDocumentStatus.CLIENT_REVIEW.value:
        raise ValueError("Document is not open for client feedback")
    old = doc.status
    doc.parent_review_status = CaseDocumentParentReviewStatus.CHANGES_REQUESTED.value
    doc.parent_feedback = message
    doc.status = CaseDocumentStatus.CHANGES_REQUESTED.value
    doc.visibility = CaseDocumentVisibility.INTERNAL_ONLY.value
    _record(
        db,
        doc,
        action="parent_feedback",
        actor_user_id=user.id,
        from_status=old,
        to_status=doc.status,
        comment=message,
    )
    db.flush()
    return doc
