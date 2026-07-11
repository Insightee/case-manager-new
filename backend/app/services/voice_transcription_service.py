"""Voice-first session log — provider-neutral speech-to-text.

transcribe_session_audio() is the only entry point business logic should use.
Providers: mock (default, deterministic for dev/tests) and OpenAI Whisper.
Retry never requires the therapist to re-record while the audio object exists.
"""

from __future__ import annotations

import json
import logging
import time
import urllib.request
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.session_audio import (
    RecordingStatus,
    SessionAudioRecording,
    TranscriptionStatus,
)
from app.storage.object_io import read_stored_bytes

logger = logging.getLogger("insightcase")

MOCK_TRANSCRIPT = (
    "Today we worked on transitions between activities. I used a visual countdown "
    "before each change and the child moved to the next activity with one verbal "
    "prompt. He seemed calm for most of the session and asked for a break once. "
    "Next time I want to try the countdown during outdoor play as well."
)


@dataclass
class TranscriptionResult:
    transcript: str
    language: Optional[str]
    provider: str
    model: str
    confidence: Optional[int]  # 0-100 where available
    processing_ms: int
    error: Optional[str] = None


def _provider() -> str:
    provider = (settings.voice_stt_provider or "mock").lower()
    if provider == "openai" and not settings.OPENAI_API_KEY:
        return "mock"
    if not settings.AI_ENABLED and provider != "mock":
        return "mock"
    return provider


def _transcribe_mock(audio_bytes: bytes) -> TranscriptionResult:
    return TranscriptionResult(
        transcript=MOCK_TRANSCRIPT,
        language="en",
        provider="mock",
        model="mock-stt-v1",
        confidence=95,
        processing_ms=0,
    )


def _multipart_body(field_specs: list[tuple[str, str]], file_field: str, filename: str, content_type: str, data: bytes) -> tuple[bytes, str]:
    boundary = uuid.uuid4().hex
    lines: list[bytes] = []
    for name, value in field_specs:
        lines.append(f"--{boundary}\r\n".encode())
        lines.append(f'Content-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode())
    lines.append(f"--{boundary}\r\n".encode())
    lines.append(
        f'Content-Disposition: form-data; name="{file_field}"; filename="{filename}"\r\n'
        f"Content-Type: {content_type}\r\n\r\n".encode()
    )
    lines.append(data)
    lines.append(f"\r\n--{boundary}--\r\n".encode())
    return b"".join(lines), boundary


def _transcribe_openai(audio_bytes: bytes, mime_type: str) -> TranscriptionResult:
    model = settings.voice_stt_model or "whisper-1"
    ext = "webm" if "webm" in (mime_type or "") else "m4a" if "mp4" in (mime_type or "") else "wav"
    started = time.monotonic()
    body, boundary = _multipart_body(
        [("model", model), ("response_format", "verbose_json")],
        "file",
        f"session-audio.{ext}",
        mime_type or "audio/webm",
        audio_bytes,
    )
    req = urllib.request.Request(
        "https://api.openai.com/v1/audio/transcriptions",
        data=body,
        headers={
            "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        payload = json.loads(resp.read().decode())
    elapsed_ms = int((time.monotonic() - started) * 1000)
    return TranscriptionResult(
        transcript=(payload.get("text") or "").strip(),
        language=payload.get("language"),
        provider="openai",
        model=model,
        confidence=None,
        processing_ms=elapsed_ms,
    )


def transcribe_audio_bytes(audio_bytes: bytes, mime_type: str) -> TranscriptionResult:
    provider = _provider()
    if provider == "openai":
        return _transcribe_openai(audio_bytes, mime_type)
    return _transcribe_mock(audio_bytes)


def transcribe_session_audio(db: Session, recording: SessionAudioRecording) -> SessionAudioRecording:
    """Run STT for one recording row and persist the outcome. Never raises —
    failures land on the row so the frontend can offer retry."""
    recording.transcription_status = TranscriptionStatus.RUNNING.value
    recording.recording_status = RecordingStatus.PROCESSING.value
    recording.error_message = None
    db.commit()

    try:
        audio_bytes = read_stored_bytes(recording.storage_key)
        result = transcribe_audio_bytes(audio_bytes, recording.mime_type)
        if not result.transcript:
            raise ValueError("Transcription returned empty text")
        recording.transcript = result.transcript
        recording.transcript_language = result.language
        recording.transcript_provider = result.provider
        recording.transcript_model = result.model
        recording.transcript_confidence = result.confidence
        recording.processing_ms = result.processing_ms
        recording.transcription_status = TranscriptionStatus.COMPLETED.value
        if settings.voice_audio_retention_days > 0 and not recording.retention_expires_at:
            recording.retention_expires_at = datetime.now(timezone.utc) + timedelta(
                days=settings.voice_audio_retention_days
            )
    except Exception as exc:  # noqa: BLE001 — failure must reach the status row
        logger.exception("Voice transcription failed for recording %s", recording.id)
        recording.transcription_status = TranscriptionStatus.FAILED.value
        recording.recording_status = RecordingStatus.FAILED.value
        recording.error_message = str(exc)[:2000]
    db.commit()
    return recording
