from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from sqlalchemy import DateTime, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class EmailLogStatus(str, Enum):
    QUEUED = "queued"
    SENT = "sent"
    FAILED = "failed"


class EmailLog(Base):
    __tablename__ = "email_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    recipient_email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    recipient_role: Mapped[Optional[str]] = mapped_column(String(64))
    subject: Mapped[str] = mapped_column(String(512), nullable=False)
    template_key: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    provider: Mapped[str] = mapped_column(String(32), nullable=False, default="smtp")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=EmailLogStatus.QUEUED.value, index=True)
    provider_message_id: Mapped[Optional[str]] = mapped_column(String(255))
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
