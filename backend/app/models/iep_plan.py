from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.visibility import VisibilityStatus


class IepPlanStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    INTERNAL_REVIEW = "INTERNAL_REVIEW"
    SHARED_WITH_PARENT = "SHARED_WITH_PARENT"
    PARENT_ACKNOWLEDGED = "PARENT_ACKNOWLEDGED"
    EDITS_SUGGESTED = "EDITS_SUGGESTED"
    APPROVED = "APPROVED"


class IepPlan(Base):
    """Structured IEP document built by case manager; may link to uploaded PDF attachment."""

    __tablename__ = "iep_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(32), nullable=False, default="v1")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=IepPlanStatus.DRAFT.value)
    sections_json: Mapped[Optional[str]] = mapped_column(Text)
    visibility_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=VisibilityStatus.INTERNAL_ONLY.value
    )
    attachment_id: Mapped[Optional[int]] = mapped_column(ForeignKey("attachments.id"))
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
