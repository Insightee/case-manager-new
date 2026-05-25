from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.case_document import (
    CaseDocument,
    CaseDocumentParentReviewStatus,
    CaseDocumentStatus,
    CaseDocumentVisibility,
    CaseDocumentWorkflowEvent,
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
    doc.status = CaseDocumentStatus.SUPERVISOR_REVIEW.value
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
    if doc.status not in (
        CaseDocumentStatus.SUBMITTED.value,
        CaseDocumentStatus.SUPERVISOR_REVIEW.value,
    ):
        raise ValueError("Document is not awaiting review")
    old = doc.status
    doc.status = CaseDocumentStatus.APPROVED.value
    doc.reviewer_user_id = user.id
    doc.visibility = visibility or CaseDocumentVisibility.CLIENT_VISIBLE_AFTER_APPROVAL.value
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
    if doc.status not in (
        CaseDocumentStatus.SUBMITTED.value,
        CaseDocumentStatus.SUPERVISOR_REVIEW.value,
    ):
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
