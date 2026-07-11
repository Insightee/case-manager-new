"""Append-only audit trail for session actual-time edits."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class SessionTimeAuditEvent(Base):
    __tablename__ = "session_time_audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"), nullable=False, index=True)
    actor_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    previous_start_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    previous_end_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    new_start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    new_end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    edit_reason: Mapped[str] = mapped_column(String(512), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
