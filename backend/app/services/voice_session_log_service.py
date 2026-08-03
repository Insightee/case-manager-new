"""Voice-first session log — upload, pipeline orchestration, status.

Pipeline (FastAPI BackgroundTasks — no queue infra in V1):
    upload → session_audio_recordings row → transcribe → extract → READY

The therapist can leave the page; status is persisted server-side and polled
via GET /daily-logs/voice/{id}/status. Failures land on the row with a retry
path that reuses the stored audio (no re-recording).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.feature_flags import voice_session_v2_active
from app.models.session import Session as TherapySession
from app.models.session_audio import (
    ExtractionStatus,
    RecordingStatus,
    SessionAudioRecording,
    TranscriptionStatus,
)
from app.models.user import User
from app.services import session_log_extraction_service, voice_transcription_service
from app.services.voice_transcription_service import _provider as stt_provider
from app.storage.object_io import delete_stored_object, put_stored_bytes

logger = logging.getLogger("insightcase")


def pipeline_runs_inline() -> bool:
    """Mock STT is instant — run synchronously so upload response is already READY."""
    return stt_provider() == "mock"

ALLOWED_AUDIO_MIME_PREFIXES = ("audio/",)
ALLOWED_AUDIO_MIME_EXPLICIT = {"video/webm"}  # Safari MediaRecorder may label audio-only webm as video/webm


def _validate_upload(mime_type: str, size_bytes: int, duration_seconds: Optional[int]) -> None:
    mime = (mime_type or "").split(";")[0].strip().lower()
    if not (mime.startswith(ALLOWED_AUDIO_MIME_PREFIXES) or mime in ALLOWED_AUDIO_MIME_EXPLICIT):
        raise HTTPException(status_code=400, detail="Let's use an audio recording here — this file type isn't supported.")
    if size_bytes <= 0:
        raise HTTPException(status_code=400, detail="The recording looks empty — let's try recording again.")
    if size_bytes > settings.voice_max_audio_bytes:
        limit_mb = settings.voice_max_audio_bytes // (1024 * 1024)
        raise HTTPException(status_code=400, detail=f"Recordings need to stay under {limit_mb} MB — a shorter take will work.")
    if duration_seconds is not None and duration_seconds > settings.voice_max_recording_seconds + 10:
        raise HTTPException(
            status_code=400,
            detail=f"Recordings are capped at {settings.voice_max_recording_seconds} seconds.",
        )


def create_recording(
    db: Session,
    *,
    session: TherapySession,
    therapist: User,
    data: bytes,
    mime_type: str,
    duration_seconds: Optional[int],
) -> SessionAudioRecording:
    _validate_upload(mime_type, len(data), duration_seconds)
    mime = (mime_type or "audio/webm").split(";")[0].strip().lower()
    ext = "webm" if "webm" in mime else "m4a" if "mp4" in mime else "audio"
    storage_key, _provider = put_stored_bytes(
        "session-voice",
        f"case_{session.case_id}",
        f"session_{session.id}",
        filename=f"voice-log.{ext}",
        data=data,
        content_type=mime,
    )
    recording = SessionAudioRecording(
        session_id=session.id,
        case_id=session.case_id,
        therapist_id=therapist.id,
        storage_key=storage_key,
        mime_type=mime,
        size_bytes=len(data),
        duration_seconds=duration_seconds,
        recording_status=RecordingStatus.UPLOADED.value,
        transcription_status=TranscriptionStatus.PENDING.value,
        extraction_status=ExtractionStatus.PENDING.value,
    )
    db.add(recording)
    db.commit()
    db.refresh(recording)
    return recording


def run_pipeline(recording_id: int) -> None:
    """BackgroundTasks entrypoint — owns its DB session."""
    db = SessionLocal()
    try:
        recording = db.get(SessionAudioRecording, recording_id)
        if not recording:
            return
        recording = voice_transcription_service.transcribe_session_audio(db, recording)
        if recording.transcription_status != TranscriptionStatus.COMPLETED.value:
            return
        session_log_extraction_service.extract_for_recording(db, recording)
        recording = db.get(SessionAudioRecording, recording_id)
        if recording and recording.extraction_status in (
            ExtractionStatus.COMPLETED.value,
            ExtractionStatus.PARTIAL.value,
        ):
            recording.recording_status = RecordingStatus.READY.value
            db.commit()
    except Exception:  # noqa: BLE001 — background task must not crash the worker
        logger.exception("Voice pipeline failed for recording %s", recording_id)
        db.rollback()
        recording = db.get(SessionAudioRecording, recording_id)
        if recording:
            recording.recording_status = RecordingStatus.FAILED.value
            recording.error_message = recording.error_message or "Processing failed — you can retry."
            db.commit()
    finally:
        db.close()


def retry_recording(db: Session, recording: SessionAudioRecording) -> SessionAudioRecording:
    if recording.recording_status == RecordingStatus.EXPIRED.value:
        raise HTTPException(status_code=410, detail="This recording has expired — let's record a fresh update.")
    recording.recording_status = RecordingStatus.UPLOADED.value
    if recording.transcription_status != TranscriptionStatus.COMPLETED.value:
        recording.transcription_status = TranscriptionStatus.PENDING.value
    recording.extraction_status = ExtractionStatus.PENDING.value
    recording.error_message = None
    db.commit()
    db.refresh(recording)
    return recording


def get_owned_recording(db: Session, recording_id: int, user: User) -> SessionAudioRecording:
    recording = db.get(SessionAudioRecording, recording_id)
    if not recording:
        raise HTTPException(status_code=404, detail="Recording not found")
    if recording.therapist_id != user.id:
        raise HTTPException(status_code=403, detail="Recording access denied")
    return recording


def _pipeline_phase(recording: SessionAudioRecording) -> str:
    if recording.recording_status == RecordingStatus.FAILED.value:
        return "failed"
    if recording.recording_status == RecordingStatus.READY.value:
        return "ready"
    if recording.transcription_status in (TranscriptionStatus.PENDING.value, TranscriptionStatus.RUNNING.value):
        return "transcribing"
    if voice_session_v2_active():
        if recording.extraction_status in (ExtractionStatus.PENDING.value, ExtractionStatus.RUNNING.value):
            return "organising_evidence"
        if recording.extraction_status in (ExtractionStatus.COMPLETED.value, ExtractionStatus.PARTIAL.value):
            if recording.recording_status != RecordingStatus.READY.value:
                return "preparing_review"
            return "ready"
        return "organising_evidence"
    if recording.extraction_status in (ExtractionStatus.PENDING.value, ExtractionStatus.RUNNING.value):
        if recording.extraction_status == ExtractionStatus.RUNNING.value:
            return "matching_strategies"
        return "identifying_goals"
    if recording.extraction_status in (ExtractionStatus.COMPLETED.value, ExtractionStatus.PARTIAL.value):
        if recording.recording_status != RecordingStatus.READY.value:
            return "creating_parent_summary"
        return "ready"
    return "identifying_observations"


def recording_status_read(recording: SessionAudioRecording, db: Session | None = None) -> dict[str, Any]:
    extraction: Optional[dict[str, Any]] = None
    structured_session: Optional[dict[str, Any]] = None
    if recording.extraction_json:
        try:
            extraction = json.loads(recording.extraction_json)
        except json.JSONDecodeError:
            extraction = None
    review_count = 0
    if extraction:
        from app.schemas.voice_session_log import VoiceSessionLogExtraction

        try:
            ext = VoiceSessionLogExtraction.model_validate(extraction)
            sse = ext.to_structured_session_evidence(
                session_id=recording.session_id,
                recording_id=recording.id,
                transcript=recording.transcript or "",
            )
            structured_session = sse.to_json_dict()
            if recording.case_id and voice_session_v2_active() and db is not None:
                from app.services.session_clinical_insight_service import build_session_clinical_insights

                structured_session["session_insights"] = build_session_clinical_insights(
                    db,
                    case_id=recording.case_id,
                    session_id=recording.session_id,
                    structured=structured_session,
                    extraction_insights=extraction.get("session_insights"),
                )
            review_count = sse.pending_review_count() + len(sse.ai_metadata.review_items)
        except Exception:
            structured_session = None
    phase = _pipeline_phase(recording)
    now = datetime.now(timezone.utc)
    expires = recording.retention_expires_at
    if expires is not None and expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    audio_available = bool(
        expires
        and expires > now
        and recording.recording_status != RecordingStatus.EXPIRED.value
    )
    return {
        "id": recording.id,
        "session_id": recording.session_id,
        "case_id": recording.case_id,
        "daily_log_id": recording.daily_log_id,
        "recording_status": recording.recording_status,
        "transcription_status": recording.transcription_status,
        "extraction_status": recording.extraction_status,
        "pipeline_phase": phase,
        "pipeline_version": "v2" if voice_session_v2_active() else "v1",
        "review_items_count": review_count,
        "transcript": recording.transcript if recording.transcription_status == TranscriptionStatus.COMPLETED.value else None,
        "transcript_language": recording.transcript_language,
        "duration_seconds": recording.duration_seconds,
        "extraction": extraction,
        "structured_session": structured_session,
        "error_message": recording.error_message,
        "audio_available": audio_available,
        "retention_expires_at": recording.retention_expires_at,
        "created_at": recording.created_at,
        "updated_at": recording.updated_at,
    }


def get_recording_audio_bytes(db: Session, recording: SessionAudioRecording) -> tuple[bytes, str]:
    """Return audio bytes + mime for replay while retention is active."""
    from app.storage.object_io import read_stored_bytes

    if recording.retention_expires_at and recording.retention_expires_at.tzinfo is None:
        expires_at = recording.retention_expires_at.replace(tzinfo=timezone.utc)
    else:
        expires_at = recording.retention_expires_at
    if recording.recording_status == RecordingStatus.EXPIRED.value:
        raise HTTPException(status_code=410, detail="This recording has expired — transcript and notes are still here.")
    if expires_at and expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=410, detail="This recording has expired — transcript and notes are still here.")
    try:
        data = read_stored_bytes(recording.storage_key)
    except Exception as exc:
        raise HTTPException(status_code=404, detail="Recording file is no longer available.") from exc
    return data, recording.mime_type or "audio/webm"


def purge_expired_audio(db: Session, *, limit: int = 100) -> int:
    """Retention job: delete raw audio past retention_expires_at; keep the row+transcript."""
    now = datetime.now(timezone.utc)
    rows = db.scalars(
        select(SessionAudioRecording)
        .where(
            SessionAudioRecording.retention_expires_at.is_not(None),
            SessionAudioRecording.retention_expires_at < now,
            SessionAudioRecording.recording_status != RecordingStatus.EXPIRED.value,
        )
        .limit(limit)
    ).all()
    for row in rows:
        try:
            delete_stored_object(row.storage_key)
        except Exception:  # noqa: BLE001
            logger.warning("Could not delete expired voice audio %s", row.id)
            continue
        row.recording_status = RecordingStatus.EXPIRED.value
    if rows:
        db.commit()
    return len(rows)
