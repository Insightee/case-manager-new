from __future__ import annotations

import re
from datetime import datetime, timezone
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.constants.therapist_vault import (
    ALL_SLOT_KEYS,
    FIXED_VAULT_SLOTS,
    OTHER_CERTIFICATION_SLOT,
    slot_for_key,
)
from app.core.config import settings
from app.models.therapist_vault_document import TherapistVaultDocument, TherapistVaultDocumentStatus
from app.models.user import User
from app.services import notification_service
from app.storage.object_io import put_stored_bytes

_PDF_MIME = "application/pdf"
_SAFE_NAME = re.compile(r"[^a-zA-Z0-9._-]+")


def _validate_pdf(content: bytes, mime: str, filename: str) -> None:
    if not content:
        raise HTTPException(status_code=400, detail="Looks like the file is empty — try choosing your PDF again.")
    if len(content) > settings.max_upload_bytes:
        mb = max(1, settings.max_upload_bytes // (1024 * 1024))
        raise HTTPException(
            status_code=413,
            detail=f"That PDF is a bit large. Please keep uploads under {mb} MB.",
        )
    normalized_mime = (mime or "").split(";")[0].strip().lower()
    name_lower = (filename or "").lower()
    if normalized_mime != _PDF_MIME and not name_lower.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Vault documents need to be PDF files.")


def _latest_for_slot(db: Session, therapist_user_id: int, slot_key: str) -> TherapistVaultDocument | None:
    return db.scalars(
        select(TherapistVaultDocument)
        .where(
            TherapistVaultDocument.therapist_user_id == therapist_user_id,
            TherapistVaultDocument.slot_key == slot_key,
        )
        .order_by(TherapistVaultDocument.id.desc())
        .limit(1)
    ).first()


def _can_upload_fixed(latest: TherapistVaultDocument | None) -> bool:
    if latest is None:
        return True
    if latest.status == TherapistVaultDocumentStatus.APPROVED:
        return False
    if latest.status == TherapistVaultDocumentStatus.PENDING:
        return False
    return latest.status == TherapistVaultDocumentStatus.REJECTED


def _can_upload_other(latest: TherapistVaultDocument | None) -> bool:
    if latest is None:
        return True
    if latest.status in (TherapistVaultDocumentStatus.APPROVED, TherapistVaultDocumentStatus.PENDING):
        return False
    return latest.status == TherapistVaultDocumentStatus.REJECTED


def _next_version(db: Session, therapist_user_id: int, slot_key: str) -> int:
    current = db.scalar(
        select(func.max(TherapistVaultDocument.version)).where(
            TherapistVaultDocument.therapist_user_id == therapist_user_id,
            TherapistVaultDocument.slot_key == slot_key,
        )
    )
    return int(current or 0) + 1


def _doc_to_read(doc: TherapistVaultDocument | None, *, can_upload: bool) -> dict | None:
    if not doc:
        return None
    slot = slot_for_key(doc.slot_key)
    return {
        "id": doc.id,
        "slot_key": doc.slot_key,
        "slot_label": slot.label if slot else doc.slot_key,
        "version": doc.version,
        "status": doc.status.value,
        "file_name": doc.file_name,
        "mime_type": doc.mime_type,
        "size_bytes": doc.size_bytes,
        "uploaded_at": doc.created_at,
        "can_upload": can_upload,
        "can_preview": True,
        "rejection_reason": doc.rejection_reason,
        "reviewed_at": doc.reviewed_at,
    }


def therapist_vault_overview(db: Session, therapist_user_id: int) -> dict:
    fixed_documents: list[dict] = []
    for slot in FIXED_VAULT_SLOTS:
        latest = _latest_for_slot(db, therapist_user_id, slot.key)
        can_upload = _can_upload_fixed(latest)
        if latest:
            fixed_documents.append(_doc_to_read(latest, can_upload=can_upload))
        else:
            fixed_documents.append(
                {
                    "id": None,
                    "slot_key": slot.key,
                    "slot_label": slot.label,
                    "version": 0,
                    "status": "MISSING",
                    "file_name": None,
                    "mime_type": _PDF_MIME,
                    "size_bytes": 0,
                    "uploaded_at": None,
                    "can_upload": True,
                    "can_preview": False,
                    "rejection_reason": None,
                    "reviewed_at": None,
                }
            )

    other_rows = db.scalars(
        select(TherapistVaultDocument)
        .where(
            TherapistVaultDocument.therapist_user_id == therapist_user_id,
            TherapistVaultDocument.slot_key == OTHER_CERTIFICATION_SLOT.key,
        )
        .order_by(TherapistVaultDocument.id.desc())
    ).all()
    active_other: list[TherapistVaultDocument] = []
    seen_replaced: set[int] = set()
    for row in other_rows:
        if row.replaces_document_id:
            seen_replaced.add(row.replaces_document_id)
    for row in other_rows:
        if row.id in seen_replaced and row.status == TherapistVaultDocumentStatus.REJECTED:
            continue
        if row.status == TherapistVaultDocumentStatus.REJECTED:
            if any(r.replaces_document_id == row.id for r in other_rows):
                continue
        active_other.append(row)

    other_certifications = []
    for doc in sorted(active_other, key=lambda d: d.id):
        other_certifications.append(_doc_to_read(doc, can_upload=_can_upload_other(doc)))

    slots = [
        {"key": s.key, "label": s.label, "help_text": s.help_text, "allow_multiple": s.allow_multiple}
        for s in FIXED_VAULT_SLOTS
    ]
    slots.append(
        {
            "key": OTHER_CERTIFICATION_SLOT.key,
            "label": OTHER_CERTIFICATION_SLOT.label,
            "help_text": OTHER_CERTIFICATION_SLOT.help_text,
            "allow_multiple": True,
        }
    )
    return {
        "slots": slots,
        "fixed_documents": fixed_documents,
        "other_certifications": other_certifications,
        "max_upload_bytes": settings.max_upload_bytes,
    }


def upload_vault_document(
    db: Session,
    *,
    therapist_user: User,
    actor: User,
    slot_key: str,
    content: bytes,
    filename: str,
    mime_type: str,
    replaces_document_id: int | None = None,
) -> TherapistVaultDocument:
    if slot_key not in ALL_SLOT_KEYS:
        raise HTTPException(status_code=400, detail="That document type is not recognized.")
    _validate_pdf(content, mime_type, filename)

    if actor.id != therapist_user.id:
        raise HTTPException(status_code=403, detail="Therapists can only upload to their own vault.")

    safe_name = _SAFE_NAME.sub("_", (filename or "document.pdf").strip())[:120] or "document.pdf"
    if not safe_name.lower().endswith(".pdf"):
        safe_name = f"{safe_name}.pdf"

    is_other = slot_key == OTHER_CERTIFICATION_SLOT.key
    latest = _latest_for_slot(db, therapist_user.id, slot_key) if not is_other else None

    if not is_other:
        if not _can_upload_fixed(latest):
            if latest and latest.status == TherapistVaultDocumentStatus.APPROVED:
                raise HTTPException(status_code=400, detail="This document is already approved and cannot be changed.")
            raise HTTPException(
                status_code=400,
                detail="This document is already waiting for review — we will let you know when it is done.",
            )
        replaces_document_id = latest.id if latest and latest.status == TherapistVaultDocumentStatus.REJECTED else None
    else:
        if replaces_document_id:
            prior = db.get(TherapistVaultDocument, replaces_document_id)
            if (
                not prior
                or prior.therapist_user_id != therapist_user.id
                or prior.slot_key != slot_key
                or prior.status != TherapistVaultDocumentStatus.REJECTED
            ):
                raise HTTPException(status_code=400, detail="Could not attach to that previous upload.")
    storage_key, _provider = put_stored_bytes(
        "therapist_vault",
        f"user_{therapist_user.id}",
        slot_key,
        filename=safe_name,
        data=content,
        content_type=_PDF_MIME,
    )

    version = _next_version(db, therapist_user.id, slot_key)
    doc = TherapistVaultDocument(
        therapist_user_id=therapist_user.id,
        slot_key=slot_key,
        version=version,
        status=TherapistVaultDocumentStatus.PENDING,
        file_name=safe_name,
        file_path=storage_key,
        mime_type=_PDF_MIME,
        size_bytes=len(content),
        uploaded_by_user_id=actor.id,
        replaces_document_id=replaces_document_id,
    )
    db.add(doc)
    db.flush()
    return doc


def get_document_for_therapist(db: Session, therapist_user_id: int, document_id: int) -> TherapistVaultDocument:
    doc = db.get(TherapistVaultDocument, document_id)
    if not doc or doc.therapist_user_id != therapist_user_id:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


def get_document_for_admin(db: Session, therapist_user_id: int, document_id: int) -> TherapistVaultDocument:
    doc = db.get(TherapistVaultDocument, document_id)
    if not doc or doc.therapist_user_id != therapist_user_id:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


def admin_vault_overview(db: Session, therapist_user_id: int) -> dict:
    overview = therapist_vault_overview(db, therapist_user_id)
    history_by_slot: dict[str, list[dict]] = {}
    rows = db.scalars(
        select(TherapistVaultDocument)
        .where(TherapistVaultDocument.therapist_user_id == therapist_user_id)
        .order_by(TherapistVaultDocument.slot_key, TherapistVaultDocument.id.desc())
    ).all()
    reviewer_ids = {r.reviewed_by_user_id for r in rows if r.reviewed_by_user_id}
    reviewer_names: dict[int, str] = {}
    if reviewer_ids:
        for u in db.scalars(select(User).where(User.id.in_(reviewer_ids))).all():
            reviewer_names[u.id] = u.full_name or u.email or f"User {u.id}"

    for row in rows:
        history_by_slot.setdefault(row.slot_key, []).append(
            {
                "id": row.id,
                "slot_key": row.slot_key,
                "version": row.version,
                "status": row.status.value,
                "file_name": row.file_name,
                "uploaded_at": row.created_at,
                "rejection_reason": row.rejection_reason,
                "reviewed_at": row.reviewed_at,
                "reviewer_name": reviewer_names.get(row.reviewed_by_user_id) if row.reviewed_by_user_id else None,
            }
        )

    return {
        "therapist_user_id": therapist_user_id,
        "fixed_documents": overview["fixed_documents"],
        "other_certifications": overview["other_certifications"],
        "history_by_slot": history_by_slot,
    }


def review_document(
    db: Session,
    *,
    reviewer: User,
    therapist_user_id: int,
    document_id: int,
    approve: bool,
    rejection_reason: str | None,
) -> TherapistVaultDocument:
    doc = get_document_for_admin(db, therapist_user_id, document_id)
    if doc.status != TherapistVaultDocumentStatus.PENDING:
        raise HTTPException(status_code=400, detail="Only pending documents can be reviewed.")

    slot = slot_for_key(doc.slot_key)
    slot_label = slot.label if slot else doc.slot_key

    if approve:
        doc.status = TherapistVaultDocumentStatus.APPROVED
        doc.rejection_reason = None
        title = "Vault document approved"
        body = f"Your {slot_label} has been approved."
        target_status = "APPROVED"
    else:
        reason = (rejection_reason or "").strip()
        if not reason:
            raise HTTPException(status_code=400, detail="Please share a short note so the therapist knows what to fix.")
        doc.status = TherapistVaultDocumentStatus.REJECTED
        doc.rejection_reason = reason
        title = "Vault document needs another look"
        body = f"Your {slot_label} was not approved yet. Note from our team: {reason}"
        target_status = "REJECTED"

    doc.reviewed_by_user_id = reviewer.id
    doc.reviewed_at = datetime.now(timezone.utc)

    dedupe_key = notification_service.notification_dedupe_key(
        "vault_document_review",
        "therapist_vault_document",
        doc.id,
        target_status,
    )
    notification_service.create_notification(
        db,
        user_id=doc.therapist_user_id,
        title=title,
        body=body,
        entity_type="therapist_vault_document",
        entity_id=doc.id,
        dedupe_key=dedupe_key,
    )
    db.flush()
    return doc
