"""Voice-first session log — audio recording + processing state.

One row per uploaded therapist voice note. Tracks upload, transcription and
extraction lifecycle so the therapist can leave the page and return while the
backend pipeline finishes. The DailyLog schema is untouched: extraction output
prefills the existing session_evidence v2 payload + DailyLog fields on submit.
"""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class RecordingStatus(str, enum.Enum):
    UPLOADED = "UPLOADED"
    PROCESSING = "PROCESSING"
    READY = "READY"
    FAILED = "FAILED"
    EXPIRED = "EXPIRED"


class TranscriptionStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ExtractionStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class SessionAudioRecording(Base):
    __tablename__ = "session_audio_recordings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Nullable: recording is uploaded before the DailyLog row exists.
    daily_log_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("daily_logs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"), nullable=False, index=True)
    case_id: Mapped[Optional[int]] = mapped_column(ForeignKey("cases.id"), nullable=True, index=True)
    therapist_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)

    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    recording_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=RecordingStatus.UPLOADED.value
    )
    transcription_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=TranscriptionStatus.PENDING.value
    )
    extraction_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=ExtractionStatus.PENDING.value
    )

    transcript: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    transcript_language: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    transcript_provider: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    transcript_model: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    transcript_confidence: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # 0-100
    processing_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Validated VoiceSessionLogExtraction JSON (see app/schemas/voice_session_log.py).
    extraction_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    retention_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
