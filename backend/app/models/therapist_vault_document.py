from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class TherapistVaultDocumentStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class TherapistVaultDocument(Base):
    __tablename__ = "therapist_vault_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    therapist_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    slot_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    status: Mapped[TherapistVaultDocumentStatus] = mapped_column(
        Enum(TherapistVaultDocumentStatus),
        default=TherapistVaultDocumentStatus.PENDING,
        nullable=False,
    )
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    uploaded_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    replaces_document_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("therapist_vault_documents.id"), nullable=True, index=True
    )
    reviewed_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    therapist = relationship("User", foreign_keys=[therapist_user_id])
    uploader = relationship("User", foreign_keys=[uploaded_by_user_id])
    reviewer = relationship("User", foreign_keys=[reviewed_by_user_id])
    replaces = relationship("TherapistVaultDocument", remote_side="TherapistVaultDocument.id")
