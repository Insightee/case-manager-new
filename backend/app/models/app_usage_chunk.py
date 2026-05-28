from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AppUsageChunk(Base):
    __tablename__ = "app_usage_chunks"
    __table_args__ = (
        UniqueConstraint("actor_user_id", "idempotency_key", name="uq_app_usage_chunks_actor_idempotency"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    session_id: Mapped[str] = mapped_column(String(96), index=True, nullable=False)
    portal: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    route: Mapped[Optional[str]] = mapped_column(String(512))
    active_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    idle_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    hidden_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    chunk_started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    chunk_ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
