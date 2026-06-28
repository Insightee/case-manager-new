from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AiGenerationLog(Base):
    __tablename__ = "ai_generation_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    case_id: Mapped[Optional[int]] = mapped_column(ForeignKey("cases.id"), index=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    provider: Mapped[str] = mapped_column(String(32), default="mock")
    model: Mapped[Optional[str]] = mapped_column(String(64))
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    token_count: Mapped[Optional[int]] = mapped_column(Integer)
    cached: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AiDraftOutput(Base):
    __tablename__ = "ai_draft_outputs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    generation_log_id: Mapped[int] = mapped_column(ForeignKey("ai_generation_logs.id", ondelete="CASCADE"), nullable=False, index=True)
    target_type: Mapped[str] = mapped_column(String(32), nullable=False)
    target_id: Mapped[Optional[int]] = mapped_column(Integer)
    draft_text: Mapped[str] = mapped_column(Text, nullable=False)
    accepted: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
