"""Voice-first session log endpoints — upload, status polling, retry.

Registered before the daily_logs router so /daily-logs/voice does not collide
with /daily-logs/{log_id}. Gated by require_voice_session_log().
"""

from __future__ import annotations

from typing import Optional

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.feature_flags import require_voice_session_log
from app.core.permissions import require_permission
from app.models.session import Session as TherapySession
from app.models.user import User
from app.services import voice_session_log_service as voice_svc

router = APIRouter(
    prefix="/daily-logs/voice",
    tags=["daily-logs"],
    dependencies=[Depends(require_voice_session_log)],
)


def _owned_session(db: Session, session_id: int, user: User) -> TherapySession:
    session = db.get(TherapySession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.therapist_user_id != user.id:
        raise HTTPException(status_code=403, detail="Session access denied")
    return session


@router.post("", status_code=status.HTTP_201_CREATED)
async def upload_voice_recording(
    background_tasks: BackgroundTasks,
    session_id: int = Form(...),
    duration_seconds: Optional[int] = Form(default=None),
    file: UploadFile = File(...),
    user: User = Depends(require_permission("daily_log.create")),
    db: Session = Depends(get_db),
):
    session = _owned_session(db, session_id, user)
    data = await file.read()
    recording = voice_svc.create_recording(
        db,
        session=session,
        therapist=user,
        data=data,
        mime_type=file.content_type or "audio/webm",
        duration_seconds=duration_seconds,
    )
    if voice_svc.pipeline_runs_inline():
        voice_svc.run_pipeline(recording.id)
        db.expire(recording)
        recording = voice_svc.get_owned_recording(db, recording.id, user)
    else:
        background_tasks.add_task(voice_svc.run_pipeline, recording.id)
    return voice_svc.recording_status_read(recording, db)


@router.get("/{recording_id}/status")
def voice_recording_status(
    recording_id: int,
    user: User = Depends(require_permission("daily_log.create")),
    db: Session = Depends(get_db),
):
    recording = voice_svc.get_owned_recording(db, recording_id, user)
    return voice_svc.recording_status_read(recording, db)


@router.post("/{recording_id}/retry")
def retry_voice_recording(
    recording_id: int,
    background_tasks: BackgroundTasks,
    user: User = Depends(require_permission("daily_log.create")),
    db: Session = Depends(get_db),
):
    recording = voice_svc.get_owned_recording(db, recording_id, user)
    recording = voice_svc.retry_recording(db, recording)
    background_tasks.add_task(voice_svc.run_pipeline, recording.id)
    return voice_svc.recording_status_read(recording, db)


@router.get("/{recording_id}/audio")
def stream_voice_recording_audio(
    recording_id: int,
    user: User = Depends(require_permission("daily_log.create")),
    db: Session = Depends(get_db),
):
    recording = voice_svc.get_owned_recording(db, recording_id, user)
    data, mime = voice_svc.get_recording_audio_bytes(db, recording)
    return Response(content=data, media_type=mime)
