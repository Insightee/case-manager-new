"""Persist structured voice session logs onto DailyLog + clinical evidence."""

from __future__ import annotations

import json
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.daily_log import DailyLog
from app.models.session_audio import SessionAudioRecording
from app.schemas.structured_session_evidence import StructuredSessionEvidence, parse_structured_session
from app.services import clinical_evidence_service as ev_svc


def apply_structured_session_to_log(
    db: Session,
    log: DailyLog,
    user,
    structured: StructuredSessionEvidence | dict[str, Any],
    *,
    recording_id: Optional[int] = None,
) -> StructuredSessionEvidence:
    """Save canonical JSON, derive prose fields, write session_evidence v2."""
    model = structured if isinstance(structured, StructuredSessionEvidence) else parse_structured_session(structured)
    log.structured_session_json = json.dumps(model.to_json_dict())
    if model.therapist_reflection:
        log.therapist_reflection = model.therapist_reflection
    derived = model.to_daily_log_fields()
    for key, value in derived.items():
        if value:
            setattr(log, key, value)
    evidence_payload = model.to_session_evidence_payload()
    if evidence_payload.get("goals") or evidence_payload.get("strategies"):
        ev_svc.save_session_evidence(
            db,
            daily_log=log,
            case_id=log.session.case_id,
            goals=evidence_payload.get("goals") or [],
            strategies=evidence_payload.get("strategies") or [],
            created_by_user_id=user.id,
            commit=False,
        )
    if recording_id:
        rec = db.get(SessionAudioRecording, recording_id)
        if rec and rec.session_id == log.session_id:
            rec.daily_log_id = log.id
    db.flush()
    return model


def structured_session_from_log(log: DailyLog) -> Optional[StructuredSessionEvidence]:
    if not log.structured_session_json:
        return None
    try:
        return parse_structured_session(log.structured_session_json)
    except Exception:
        return None
