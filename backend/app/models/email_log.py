from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from sqlalchemy import DateTime, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class EmailLogStatus(str, Enum):
    QUEUED = "queued"
    SENT = "sent"  # legacy alias for accepted
    ACCEPTED = "accepted"
    DELIVERED = "delivered"
    FAILED = "failed"  # legacy
    FAILED_RETRYING = "failed_retrying"
    FAILED_FINAL = "failed_final"
    HARD_BOUNCED = "hard_bounced"
    SOFT_BOUNCED = "soft_bounced"
    PROCESS_FAILED = "process_failed"
    PENDING = "pending"
    SKIPPED_SUPPRESSED = "skipped_suppressed"
    SKIPPED_RATE_LIMITED = "skipped_rate_limited"
    SKIPPED_DUPLICATE = "skipped_duplicate"
    SKIPPED_INVALID_EMAIL = "skipped_invalid_email"


LOGIN_TEMPLATE_KEYS = frozenset({"portal_invite", "password_reset"})
TRANSACTIONAL_DEDUPE_TEMPLATE_KEYS = frozenset(
    {"invoice_generated", "report_published", "payment_reminder"}
)


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
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=EmailLogStatus.QUEUED.value, index=True)
    provider_message_id: Mapped[Optional[str]] = mapped_column(String(255))
    provider_request_id: Mapped[Optional[str]] = mapped_column(String(255))
    entity_type: Mapped[Optional[str]] = mapped_column(String(64))
    entity_id: Mapped[Optional[int]] = mapped_column(Integer)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    next_retry_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_attempt_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(255), index=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
