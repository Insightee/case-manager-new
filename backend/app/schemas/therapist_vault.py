from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class VaultDocumentSlotRead(BaseModel):
    key: str
    label: str
    help_text: Optional[str] = None
    allow_multiple: bool = False


class TherapistVaultDocumentRead(BaseModel):
    id: Optional[int] = None
    slot_key: str
    slot_label: str
    version: int
    status: str
    file_name: Optional[str] = None
    mime_type: str
    size_bytes: int
    uploaded_at: Optional[datetime] = None
    can_upload: bool = False
    can_preview: bool = True
    rejection_reason: Optional[str] = None
    reviewed_at: Optional[datetime] = None


class TherapistVaultDocumentHistoryRead(BaseModel):
    id: int
    slot_key: str
    version: int
    status: str
    file_name: str
    uploaded_at: datetime
    rejection_reason: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    reviewer_name: Optional[str] = None


class TherapistVaultOverviewRead(BaseModel):
    slots: list[VaultDocumentSlotRead]
    fixed_documents: list[TherapistVaultDocumentRead]
    other_certifications: list[TherapistVaultDocumentRead]
    max_upload_bytes: int


class TherapistVaultAdminOverviewRead(BaseModel):
    therapist_user_id: int
    fixed_documents: list[TherapistVaultDocumentRead]
    other_certifications: list[TherapistVaultDocumentRead]
    history_by_slot: dict[str, list[TherapistVaultDocumentHistoryRead]] = Field(default_factory=dict)


class VaultDocumentReviewAction(BaseModel):
    rejection_reason: Optional[str] = Field(None, max_length=2000)
