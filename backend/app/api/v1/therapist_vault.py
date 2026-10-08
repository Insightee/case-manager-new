from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_request_meta
from app.core.audit import log_audit
from app.core.database import get_db
from app.core.permissions import RoleName, require_mutation_permission, require_permission
from app.models.user import User
from app.schemas.therapist_vault import (
    TherapistVaultAdminOverviewRead,
    TherapistVaultDocumentRead,
    TherapistVaultOverviewRead,
    VaultDocumentReviewAction,
)
from app.services import therapist_vault_service as vault_svc
from app.storage.object_io import stored_file_response

router = APIRouter(prefix="/therapist/vault", tags=["therapist-vault"])


def _require_therapist(user: User) -> None:
    if RoleName.THERAPIST.value not in user.role_names:
        raise HTTPException(status_code=403, detail="Therapist access only")


@router.get("/documents", response_model=TherapistVaultOverviewRead)
def list_my_vault_documents(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_therapist(user)
    return TherapistVaultOverviewRead(**vault_svc.therapist_vault_overview(db, user.id))


@router.post("/documents/upload", response_model=TherapistVaultDocumentRead, status_code=status.HTTP_201_CREATED)
async def upload_my_vault_document(
    slot_key: str = Form(...),
    replaces_document_id: Optional[int] = Form(None),
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_therapist(user)
    content = await file.read()
    doc = vault_svc.upload_vault_document(
        db,
        therapist_user=user,
        actor=user,
        slot_key=slot_key.strip(),
        content=content,
        filename=file.filename or "document.pdf",
        mime_type=file.content_type or "application/pdf",
        replaces_document_id=replaces_document_id,
    )
    db.commit()
    db.refresh(doc)
    overview = vault_svc.therapist_vault_overview(db, user.id)
    for bucket in (overview["fixed_documents"], overview["other_certifications"]):
        for row in bucket:
            if row.get("id") == doc.id:
                return TherapistVaultDocumentRead(**row)
    from app.constants.therapist_vault import slot_for_key

    slot_meta = slot_for_key(doc.slot_key)
    return TherapistVaultDocumentRead(
        id=doc.id,
        slot_key=doc.slot_key,
        slot_label=slot_meta.label if slot_meta else doc.slot_key,
        version=doc.version,
        status=doc.status.value,
        file_name=doc.file_name,
        mime_type=doc.mime_type,
        size_bytes=doc.size_bytes,
        uploaded_at=doc.created_at,
        can_upload=False,
        can_preview=True,
    )


@router.get("/documents/{document_id}/file")
def download_my_vault_document(
    document_id: int,
    inline: bool = False,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_therapist(user)
    doc = vault_svc.get_document_for_therapist(db, user.id, document_id)
    return stored_file_response(
        doc.file_path,
        filename=doc.file_name,
        media_type=doc.mime_type,
        inline=inline,
    )


admin_router = APIRouter(prefix="/admin/therapist-profiles", tags=["therapist-vault-admin"])


@admin_router.get("/{user_id}/vault/documents", response_model=TherapistVaultAdminOverviewRead)
def admin_list_therapist_vault(
    user_id: int,
    user: User = Depends(require_permission("user.manage")),
    db: Session = Depends(get_db),
):
    target = db.get(User, user_id)
    if not target or RoleName.THERAPIST.value not in target.role_names:
        raise HTTPException(status_code=404, detail="Therapist not found")
    return TherapistVaultAdminOverviewRead(**vault_svc.admin_vault_overview(db, user_id))


@admin_router.get("/{user_id}/vault/documents/{document_id}/file")
def admin_download_therapist_vault_document(
    user_id: int,
    document_id: int,
    inline: bool = False,
    user: User = Depends(require_permission("user.manage")),
    db: Session = Depends(get_db),
):
    doc = vault_svc.get_document_for_admin(db, user_id, document_id)
    return stored_file_response(
        doc.file_path,
        filename=doc.file_name,
        media_type=doc.mime_type,
        inline=inline,
    )


@admin_router.post("/{user_id}/vault/documents/{document_id}/approve", response_model=TherapistVaultDocumentRead)
def admin_approve_vault_document(
    user_id: int,
    document_id: int,
    request: Request,
    user: User = Depends(require_mutation_permission("user.manage")),
    db: Session = Depends(get_db),
):
    doc = vault_svc.review_document(
        db,
        reviewer=user,
        therapist_user_id=user_id,
        document_id=document_id,
        approve=True,
        rejection_reason=None,
    )
    meta = get_request_meta(request)
    log_audit(
        db,
        actor_user_id=user.id,
        action="approve_vault_document",
        entity_type="therapist_vault_document",
        entity_id=doc.id,
        **meta,
    )
    db.commit()
    overview = vault_svc.therapist_vault_overview(db, user_id)
    for bucket in (overview["fixed_documents"], overview["other_certifications"]):
        for row in bucket:
            if row.get("id") == doc.id:
                return TherapistVaultDocumentRead(**row)
    raise HTTPException(status_code=500, detail="Document state could not be loaded")


@admin_router.post("/{user_id}/vault/documents/{document_id}/reject", response_model=TherapistVaultDocumentRead)
def admin_reject_vault_document(
    user_id: int,
    document_id: int,
    payload: VaultDocumentReviewAction,
    request: Request,
    user: User = Depends(require_mutation_permission("user.manage")),
    db: Session = Depends(get_db),
):
    doc = vault_svc.review_document(
        db,
        reviewer=user,
        therapist_user_id=user_id,
        document_id=document_id,
        approve=False,
        rejection_reason=payload.rejection_reason,
    )
    meta = get_request_meta(request)
    log_audit(
        db,
        actor_user_id=user.id,
        action="reject_vault_document",
        entity_type="therapist_vault_document",
        entity_id=doc.id,
        **meta,
    )
    db.commit()
    overview = vault_svc.therapist_vault_overview(db, user_id)
    for bucket in (overview["fixed_documents"], overview["other_certifications"]):
        for row in bucket:
            if row.get("id") == doc.id:
                return TherapistVaultDocumentRead(**row)
    raise HTTPException(status_code=500, detail="Document state could not be loaded")
