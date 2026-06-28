from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ClinicalReviewQueueItem(Base):
    __tablename__ = "clinical_review_queue_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    item_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    priority: Mapped[str] = mapped_column(String(16), default="normal", nullable=False)
    source_case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), nullable=False, index=True)
    source_goal_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    source_strategy_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    linked_library_goal_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    linked_library_strategy_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    source_entity_kind: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    source_entity_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    assigned_to_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewer_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewer_note: Mapped[Optional[str]] = mapped_column(Text)
    action_payload_json: Mapped[Optional[str]] = mapped_column(Text)
    title: Mapped[Optional[str]] = mapped_column(String(255))
    summary: Mapped[Optional[str]] = mapped_column(Text)
    parent_safe: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class ClinicalReviewQueueEvent(Base):
    __tablename__ = "clinical_review_queue_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    queue_item_id: Mapped[int] = mapped_column(
        ForeignKey("clinical_review_queue_items.id", ondelete="CASCADE"), nullable=False, index=True
    )
    actor_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    old_status: Mapped[Optional[str]] = mapped_column(String(32))
    new_status: Mapped[str] = mapped_column(String(32), nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    note: Mapped[Optional[str]] = mapped_column(Text)
    payload_json: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
