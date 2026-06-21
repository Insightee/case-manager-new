from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ClinicalSnapshot(Base):
    __tablename__ = "clinical_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), nullable=False, index=True)
    month: Mapped[str] = mapped_column(String(7), nullable=False, index=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    generated_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    generated_for_role: Mapped[str] = mapped_column(String(32), nullable=False, default="therapist")
    insight_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft", index=True)
    deterministic_summary_json: Mapped[Optional[str]] = mapped_column(Text)
    ai_output_json: Mapped[Optional[str]] = mapped_column(Text)
    ai_output_text: Mapped[Optional[str]] = mapped_column(Text)
    source_record_ids_json: Mapped[Optional[str]] = mapped_column(Text)
    reference_chunk_ids_json: Mapped[Optional[str]] = mapped_column(Text)
    prompt_version: Mapped[Optional[str]] = mapped_column(String(16))
    provider: Mapped[str] = mapped_column(String(32), default="mock")
    model: Mapped[Optional[str]] = mapped_column(String(64))
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    output_hash: Mapped[Optional[str]] = mapped_column(String(64))
    token_input_count: Mapped[Optional[int]] = mapped_column(Integer)
    token_output_count: Mapped[Optional[int]] = mapped_column(Integer)
    estimated_cost: Mapped[Optional[float]] = mapped_column(Float)
    generation_log_id: Mapped[Optional[int]] = mapped_column(ForeignKey("ai_generation_logs.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ClinicalSnapshotFeedback(Base):
    __tablename__ = "clinical_snapshot_feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    snapshot_id: Mapped[int] = mapped_column(
        ForeignKey("clinical_snapshots.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    feedback_type: Mapped[str] = mapped_column(String(32), nullable=False)
    comment: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
