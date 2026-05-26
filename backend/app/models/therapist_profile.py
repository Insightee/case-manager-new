from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class TherapistProfileStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    PAUSED = "PAUSED"


class TherapistProfile(Base):
    __tablename__ = "therapist_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, nullable=False, index=True)
    display_name: Mapped[Optional[str]] = mapped_column(String(255))
    short_bio: Mapped[Optional[str]] = mapped_column(Text)
    academic_qualifications: Mapped[Optional[str]] = mapped_column(Text)
    professional_certificates: Mapped[Optional[list]] = mapped_column(JSON, default=list)
    services_offered: Mapped[Optional[list]] = mapped_column(JSON, default=list)
    status: Mapped[TherapistProfileStatus] = mapped_column(
        Enum(TherapistProfileStatus), default=TherapistProfileStatus.DRAFT, nullable=False
    )
    license_number: Mapped[Optional[str]] = mapped_column(String(128))
    admin_note: Mapped[Optional[str]] = mapped_column(Text)
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    reviewed_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    supervisor_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    mentor_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user = relationship("User", foreign_keys=[user_id], backref="therapist_profile")
    reviewer = relationship("User", foreign_keys=[reviewed_by_user_id])
    supervisor = relationship("User", foreign_keys=[supervisor_user_id])
    mentor = relationship("User", foreign_keys=[mentor_user_id])
