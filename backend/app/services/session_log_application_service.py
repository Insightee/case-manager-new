"""Thin application entry point for session-log writes.

One submission transaction: lifecycle + structured snapshot + relational evidence + derived prose.
Delegates to existing domain services — extract sub-services only on proven duplication.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.daily_log import DailyLog, LogApprovalStatus
from app.models.user import User
from app.schemas.structured_session_evidence import StructuredSessionEvidence, parse_structured_session
from app.services import clinical_evidence_service as ev_svc
from app.services import log_service
from app.services import structured_session_log_service as sse_svc

logger = logging.getLogger("insightcase.session_log_application")

# Legacy frontend status aliases → canonical evidence states
_CONFIRMED_GOAL_STATUSES = frozenset({"confirmed", "changed", "edited_and_confirmed"})
_PENDING_IEP_STATUSES = frozenset({"pending", "suggested"})


class SessionLogValidationError(ValueError):
    """Therapist-facing validation for structured session submit."""


def _parse_structured(raw: Any) -> StructuredSessionEvidence:
    return parse_structured_session(raw)


def validate_structured_for_submit(model: StructuredSessionEvidence) -> None:
    """Reject submit when IEP-matched goals remain unresolved."""
    for goal in model.goals:
        if goal.match_type == "new_observation":
            continue
        if goal.status in _PENDING_IEP_STATUSES:
            raise SessionLogValidationError(
                f"Confirm or reject the matched goal before submitting: {goal.goal_label or 'Unnamed goal'}"
            )
    has_story = bool((model.todays_story or "").strip())
    has_confirmed = bool(model.confirmed_goals())
    if not has_story and not has_confirmed and not model.no_goal_reason:
        raise SessionLogValidationError(
            "Add what happened today, confirm at least one goal, or choose why no IEP goal was addressed."
        )


def prepare_draft(
    db: Session,
    session_id: int,
    user: User,
    *,
    recording_id: Optional[int] = None,
) -> StructuredSessionEvidence:
    """Load draft shell; optionally hydrate from voice extraction."""
    from app.models.session import Session as TherapySession
    from app.models.session_audio import SessionAudioRecording

    session = db.get(TherapySession, session_id)
    if not session:
        raise SessionLogValidationError("Session not found")
    draft = StructuredSessionEvidence(session_id=session_id, recording_id=recording_id)
    if recording_id:
        rec = db.get(SessionAudioRecording, recording_id)
        if rec and rec.session_id == session_id and rec.extraction_json:
            try:
                from app.schemas.voice_session_log import VoiceSessionLogExtraction

                extraction = VoiceSessionLogExtraction.model_validate_json(rec.extraction_json)
                draft = extraction.to_structured_session_evidence(
                    session_id=session_id,
                    recording_id=recording_id,
                    transcript=rec.transcript or "",
                )
            except Exception:
                logger.exception("prepare_draft: failed to map recording %s extraction", recording_id)
    return draft


def save_draft(
    db: Session,
    log: DailyLog,
    user: User,
    structured: StructuredSessionEvidence | dict[str, Any],
    *,
    recording_id: Optional[int] = None,
) -> DailyLog:
    """Persist structured JSON only — no relational evidence write."""
    import json

    model = structured if isinstance(structured, StructuredSessionEvidence) else _parse_structured(structured)
    log.structured_session_json = json.dumps(model.to_json_dict())
    if model.therapist_reflection:
        log.therapist_reflection = model.therapist_reflection
    if recording_id:
        from app.models.session_audio import SessionAudioRecording

        rec = db.get(SessionAudioRecording, recording_id)
        if rec and rec.session_id == log.session_id:
            rec.daily_log_id = log.id
    db.flush()
    return log


def apply_structured_to_log(
    db: Session,
    log: DailyLog,
    user: User,
    structured: StructuredSessionEvidence | dict[str, Any],
    *,
    recording_id: Optional[int] = None,
    validate_submit: bool = False,
) -> StructuredSessionEvidence:
    """Apply structured session: optional validation, snapshot, relational evidence, prose."""
    model = structured if isinstance(structured, StructuredSessionEvidence) else _parse_structured(structured)
    if validate_submit:
        validate_structured_for_submit(model)
    return sse_svc.apply_structured_session_to_log(
        db,
        log,
        user,
        model,
        recording_id=recording_id,
    )


def apply_session_evidence_payload(
    db: Session,
    log: DailyLog,
    user: User,
    *,
    goals: list[dict[str, Any]] | None = None,
    strategies: list[dict[str, Any]] | None = None,
) -> None:
    """Legacy standalone evidence — prefer structured submit."""
    if not goals and not strategies:
        return
    ev_svc.save_session_evidence(
        db,
        daily_log=log,
        case_id=log.session.case_id,
        goals=goals or [],
        strategies=strategies or [],
        created_by_user_id=user.id,
        commit=False,
    )


def evidence_payload_to_structured(
    log: DailyLog,
    goals: list[dict[str, Any]],
    strategies: list[dict[str, Any]],
) -> StructuredSessionEvidence:
    """Map deprecated PUT /session-evidence body into structured draft for resubmit."""
    existing = sse_svc.structured_session_from_log(log) or StructuredSessionEvidence(
        session_id=log.session_id,
    )
    # Preserve story/reflection; overlay confirmed goals from legacy payload
    structured_goals = []
    for g in goals:
        structured_goals.append(
            {
                "goal_card_id": g.get("goal_card_id"),
                "goal_repository_item_id": g.get("goal_repository_item_id"),
                "goal_label": g.get("goal_label") or "",
                "status": "confirmed",
                "match_type": "active_iep",
                "evidence": [g.get("measurement_note") or ""] if g.get("measurement_note") else [],
                "strategies": [
                    {
                        "strategy_id": s.get("strategy_id"),
                        "strategy_label": s.get("strategy_label") or "",
                        "feedback": s.get("strategy_feedback"),
                        "spoken_phrase": s.get("short_note") or "",
                    }
                    for s in (g.get("strategies") or [])
                ],
            }
        )
    loose = [
        {
            "strategy_id": s.get("strategy_id"),
            "strategy_label": s.get("strategy_label") or "",
            "feedback": s.get("strategy_feedback"),
            "spoken_phrase": s.get("short_note") or "",
        }
        for s in strategies
    ]
    payload = existing.model_dump()
    if structured_goals:
        payload["goals"] = structured_goals
    if loose:
        payload["strategies_session_level"] = loose
    return StructuredSessionEvidence.model_validate(payload)


def submit_log(
    db: Session,
    user: User,
    *,
    session_id: int,
    body: dict[str, Any],
    structured: Any = None,
    session_evidence: Any = None,
    recording_id: Optional[int] = None,
) -> tuple[DailyLog, bool]:
    """Create daily log + apply structured/evidence in one flow."""
    log, created = log_service.create_daily_log(db, **body)
    if structured:
        apply_structured_to_log(
            db,
            log,
            user,
            structured,
            recording_id=recording_id,
            validate_submit=True,
        )
    elif session_evidence:
        goals = session_evidence.get("goals") if isinstance(session_evidence, dict) else None
        strategies = session_evidence.get("strategies") if isinstance(session_evidence, dict) else None
        apply_session_evidence_payload(db, log, user, goals=goals, strategies=strategies)
    return log, created


def update_log(
    db: Session,
    log: DailyLog,
    user: User,
    *,
    body: dict[str, Any],
    structured: Any = None,
    session_evidence: Any = None,
    recording_id: Optional[int] = None,
) -> DailyLog:
    log = log_service.update_daily_log(db, log, user.id, **body)
    if structured:
        apply_structured_to_log(db, log, user, structured, recording_id=recording_id, validate_submit=False)
    elif session_evidence:
        goals = session_evidence.get("goals") if isinstance(session_evidence, dict) else None
        strategies = session_evidence.get("strategies") if isinstance(session_evidence, dict) else None
        apply_session_evidence_payload(db, log, user, goals=goals, strategies=strategies)
    return log


def resubmit_log(
    db: Session,
    log: DailyLog,
    user: User,
    *,
    body: dict[str, Any],
    structured: Any = None,
    session_evidence: Any = None,
    recording_id: Optional[int] = None,
) -> DailyLog:
    """Resubmit rejected log — apply structured evidence before prose validation."""
    session = log.session
    if not session or session.therapist_user_id != user.id:
        raise SessionLogValidationError("Access denied")
    from app.services.log_service import is_log_resubmittable

    if not is_log_resubmittable(log):
        raise SessionLogValidationError("Only rejected logs can be resubmitted")

    if body:
        log_service._apply_log_field_updates(log, body)

    if structured:
        apply_structured_to_log(
            db,
            log,
            user,
            structured,
            recording_id=recording_id,
            validate_submit=True,
        )
    elif session_evidence:
        goals = session_evidence.get("goals") if isinstance(session_evidence, dict) else None
        strategies = session_evidence.get("strategies") if isinstance(session_evidence, dict) else None
        apply_session_evidence_payload(db, log, user, goals=goals, strategies=strategies)
        log_service._validate_log_for_submission(log)
    else:
        log_service._validate_log_for_submission(log)

    log.approval_status = LogApprovalStatus.PENDING.value
    log.review_note = None
    log.submitted_at = datetime.now(timezone.utc)
    log.resubmitted_at = log.submitted_at
    db.flush()
    return log


def portal_payload_to_body(payload: dict[str, Any]) -> tuple[dict[str, Any], Any, Any, Optional[int]]:
    """Split therapist portal payload into log body + structured/evidence parts."""
    structured = payload.pop("structured_session_json", None)
    recording_id = payload.pop("recording_id", None)
    session_evidence = payload.pop("session_evidence", None)
    return payload, structured, session_evidence, recording_id
