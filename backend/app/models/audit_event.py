from __future__ import annotations

from typing import Optional

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor_user_id: Mapped[Optional[int ]] = mapped_column(ForeignKey("users.id"))
    case_id: Mapped[Optional[int]] = mapped_column(ForeignKey("cases.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[Optional[str ]] = mapped_column(String(64))
    actor = relationship("User", foreign_keys=[actor_user_id], lazy="select")
    old_value: Mapped[Optional[str ]] = mapped_column(Text)
    new_value: Mapped[Optional[str ]] = mapped_column(Text)
    ip_address: Mapped[Optional[str ]] = mapped_column(String(64))
    user_agent: Mapped[Optional[str ]] = mapped_column(String(512))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
