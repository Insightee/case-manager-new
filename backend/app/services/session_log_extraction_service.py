"""Voice-first session log — transcript → strict structured extraction.

extract_session_log_structure() turns a transcript plus a compact case context
into a validated VoiceSessionLogExtraction. Guardrails:
- The model only sees a small candidate set (a case has ~3–8 active goals);
  it never receives the org-wide library.
- IDs outside the provided candidate set are stripped (become candidates).
- Measurement enums are validated; invented values are dropped.
- Malformed output → PARTIAL/FAILED status; the therapist proceeds with the
  typed form and is never blocked.

Matching order (keyword/alias — pgvector deferred):
goal-linked strategies → case strategies → org pool → new candidate.
"""

from __future__ import annotations

import json
import logging
import re
import time
import urllib.request
from typing import Any, Optional

from pydantic import ValidationError
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.clinical_measurement_criteria import (
    GOAL_ACHIEVEMENT_VALUES,
    INDEPENDENCE_VALUES,
    PARTICIPATION_VALUES,
)
from app.core.config import settings
from app.models.clinical_evidence import IepGoalCard
from app.models.goal_repository import RepositoryItemStatus, StrategyRepositoryItem
from app.models.session_audio import ExtractionStatus, SessionAudioRecording
from app.schemas.voice_session_log import (
    VoiceSessionLogExtraction,
    parse_extraction_output,
)

logger = logging.getLogger("insightcase")

IEP_ASSIGNED_STATUSES = ("active", "paused")
STRATEGY_CONTEXT_STATUSES = (
    RepositoryItemStatus.ACTIVE.value,
    RepositoryItemStatus.APPROVED.value,
    RepositoryItemStatus.CANDIDATE.value,
    RepositoryItemStatus.LOCAL.value,
)
MAX_CONTEXT_STRATEGIES = 20
MAX_TRANSCRIPT_CHARS = 12000


def build_case_context(db: Session, case_id: int, *, selected_goal_card_ids: Optional[list[int]] = None) -> dict[str, Any]:
    """Compact candidate set for the extractor — ID + label + domain only."""
    goal_stmt = (
        select(IepGoalCard)
        .where(IepGoalCard.case_id == case_id, IepGoalCard.status.in_(IEP_ASSIGNED_STATUSES))
        .order_by(IepGoalCard.sort_order, IepGoalCard.id)
    )
    goal_cards = db.scalars(goal_stmt).all()
    if selected_goal_card_ids:
        selected = set(selected_goal_card_ids)
        # Selected goals first; the rest stay available for voice-detected work.
        goal_cards = sorted(goal_cards, key=lambda c: (c.id not in selected, c.sort_order or 0, c.id))

    goal_ids = [c.id for c in goal_cards]
    strat_rows = db.scalars(
        select(StrategyRepositoryItem)
        .where(
            or_(
                StrategyRepositoryItem.case_id == case_id,
                StrategyRepositoryItem.linked_goal_card_id.in_(goal_ids) if goal_ids else False,
                StrategyRepositoryItem.case_id.is_(None),
            ),
            StrategyRepositoryItem.status.in_(STRATEGY_CONTEXT_STATUSES),
        )
        .order_by(
            # goal-linked first, then case-level, then org pool
            StrategyRepositoryItem.linked_goal_card_id.is_(None),
            StrategyRepositoryItem.case_id.is_(None),
            StrategyRepositoryItem.id.desc(),
        )
        .limit(MAX_CONTEXT_STRATEGIES)
    ).all()

    return {
        "goals": [
            {"goal_card_id": c.id, "label": c.label, "domain_key": c.domain_key}
            for c in goal_cards
        ],
        "strategies": [
            {
                "strategy_id": s.id,
                "label": s.label,
                "linked_goal_card_id": s.linked_goal_card_id,
                "scope": "case" if s.case_id else "org",
            }
            for s in strat_rows
        ],
    }


def _tokenize(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]+", (text or "").lower()) if len(w) > 3}


def match_strategy_label(phrase: str, context_strategies: list[dict[str, Any]]) -> Optional[dict[str, Any]]:
    """Deterministic keyword overlap match; the therapist confirms in review."""
    phrase_tokens = _tokenize(phrase)
    if not phrase_tokens:
        return None
    best, best_score = None, 0.0
    for strat in context_strategies:
        label_tokens = _tokenize(strat.get("label") or "")
        if not label_tokens:
            continue
        overlap = len(phrase_tokens & label_tokens)
        score = overlap / len(label_tokens)
        if overlap and score > best_score:
            best, best_score = strat, score
    if best and best_score >= 0.5:
        return {**best, "match_confidence": round(best_score, 2)}
    return None


EXTRACTION_SYSTEM_PROMPT = """You extract structured therapy session log data from a therapist's spoken update.
Rules — follow all of them:
- Use ONLY goal_card_id and strategy_id values from the provided candidate lists. Never invent IDs.
- If the therapist mentions a goal or strategy not in the lists, set the id to null and fill goal_candidate_label / strategy_candidate_label instead.
- Never claim progress that the therapist did not describe. When unsure, omit the measurement field.
- participation must be one of: {participation}. independence_support_needed: {independence}. goal_achievement: {achievement}. Omit when not clearly stated.
- strategy_feedback must be one of: worked_well, partially_worked, did_not_work, not_observed — or omitted.
- Never diagnose the child. Use participation-focused, strengths-based language.
- parent_note_draft: short, warm, strengths-based, no internal/confidential detail, no unconfirmed concerns.
- internal_note_candidate: clinical detail not suitable for parents.
- missing_information: list useful details the therapist did not mention (e.g. child response to a support).
- review_flags: only for material concerns (safeguarding language, conflict with goals, very low confidence).
Return ONLY valid JSON matching the provided schema."""


def _extraction_user_prompt(transcript: str, case_context: dict[str, Any], starting_state: Optional[str]) -> str:
    schema_hint = {
        "session_summary": "",
        "goal_evidence": [
            {
                "goal_card_id": None,
                "goal_candidate_label": None,
                "goal_label": "",
                "evidence_summary": "",
                "child_response": "",
                "participation": None,
                "independence_support_needed": None,
                "goal_achievement": None,
                "confidence": 0.0,
            }
        ],
        "strategies": [
            {
                "strategy_id": None,
                "strategy_candidate_label": None,
                "strategy_label": "",
                "spoken_phrase": "",
                "implementation_summary": "",
                "child_response": "",
                "goal_index": None,
                "strategy_feedback": None,
                "match_confidence": 0.0,
            }
        ],
        "child_response_summary": "",
        "progress_summary": "",
        "barriers_or_concerns": "",
        "next_session_plan": "",
        "parent_note_draft": "",
        "internal_note_candidate": "",
        "starting_state": starting_state,
        "missing_information": [],
        "review_flags": [],
    }
    return (
        f"Candidate goals: {json.dumps(case_context['goals'])}\n"
        f"Candidate strategies: {json.dumps(case_context['strategies'])}\n"
        f"Child starting state: {starting_state or 'not recorded'}\n\n"
        f"Transcript:\n{transcript[:MAX_TRANSCRIPT_CHARS]}\n\n"
        f"JSON schema:\n{json.dumps(schema_hint)}"
    )


def _mock_extraction(transcript: str, case_context: dict[str, Any], starting_state: Optional[str]) -> dict[str, Any]:
    """Deterministic extraction for dev/tests — first goal + keyword-matched strategy."""
    goals = case_context.get("goals") or []
    strategies = case_context.get("strategies") or []
    first_goal = goals[0] if goals else None
    matched = match_strategy_label(transcript, strategies)
    sentences = [s.strip() for s in transcript.split(".") if s.strip()]
    summary = ". ".join(sentences[:2])[:1000] or transcript[:400]
    out: dict[str, Any] = {
        "session_summary": summary,
        "goal_evidence": [],
        "strategies": [],
        "child_response_summary": next((s for s in sentences if "child" in s.lower() or "he " in s.lower() or "she " in s.lower()), "")[:500],
        "progress_summary": "",
        "barriers_or_concerns": "",
        "next_session_plan": next((s for s in sentences if "next" in s.lower()), "")[:500],
        "parent_note_draft": (
            f"We had a good session today. {summary[:200]}"
        ),
        "internal_note_candidate": "",
        "starting_state": starting_state,
        "missing_information": [],
        "review_flags": [],
    }
    if first_goal:
        out["goal_evidence"].append(
            {
                "goal_card_id": first_goal["goal_card_id"],
                "goal_label": first_goal["label"],
                "evidence_summary": summary[:400],
                "child_response": out["child_response_summary"],
                "confidence": 0.6,
            }
        )
    if matched:
        out["strategies"].append(
            {
                "strategy_id": matched["strategy_id"],
                "strategy_label": matched["label"],
                "spoken_phrase": "",
                "implementation_summary": summary[:300],
                "goal_index": 0 if first_goal else None,
                "match_confidence": matched.get("match_confidence", 0.5),
            }
        )
    if not out["child_response_summary"]:
        out["missing_information"].append("How the child responded to the supports used")
    return out


def _call_openai_extraction(system: str, user: str) -> dict[str, Any]:
    model = settings.SESSION_LOG_MODEL or settings.AI_DEFAULT_MODEL or "gpt-4o-mini"
    body = json.dumps(
        {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.2,
        }
    ).encode()
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=body,
        headers={
            "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=90) as resp:
        data = json.loads(resp.read().decode())
    return json.loads(data["choices"][0]["message"]["content"])


def _extraction_provider() -> str:
    if not settings.AI_ENABLED:
        return "mock"
    provider = (settings.AI_PROVIDER or "mock").lower()
    if provider == "openai" and settings.OPENAI_API_KEY:
        return "openai"
    return "mock"


def extract_session_log_structure(
    transcript: str,
    case_context: dict[str, Any],
    *,
    starting_state: Optional[str] = None,
) -> VoiceSessionLogExtraction:
    """Provider-neutral extraction with strict schema validation.

    Raises ValidationError / ValueError on malformed output — callers decide
    how to degrade (extract_for_recording maps it to PARTIAL/FAILED).
    """
    provider = _extraction_provider()
    if provider == "openai":
        system = EXTRACTION_SYSTEM_PROMPT.format(
            participation=", ".join(PARTICIPATION_VALUES),
            independence=", ".join(INDEPENDENCE_VALUES),
            achievement=", ".join(GOAL_ACHIEVEMENT_VALUES),
        )
        raw = _call_openai_extraction(system, _extraction_user_prompt(transcript, case_context, starting_state))
    else:
        raw = _mock_extraction(transcript, case_context, starting_state)

    extraction = parse_extraction_output(raw)
    allowed_goal_ids = {g["goal_card_id"] for g in case_context.get("goals", [])}
    allowed_strategy_ids = {s["strategy_id"] for s in case_context.get("strategies", [])}
    return extraction.validated_against(
        allowed_goal_card_ids=allowed_goal_ids,
        allowed_strategy_ids=allowed_strategy_ids,
    )


def extract_for_recording(db: Session, recording: SessionAudioRecording) -> SessionAudioRecording:
    """Pipeline step: run extraction for a transcribed recording and persist
    the outcome on the row. Never raises."""
    from app.core.feature_flags import clinical_language_engine_active, voice_session_v2_active
    from app.services.clinical_language_engine_service import extract_with_cle_if_active
    from app.services.session_context_builder import build_session_interpretation_context

    if not recording.transcript:
        recording.extraction_status = ExtractionStatus.SKIPPED.value
        db.commit()
        return recording
    if not recording.case_id:
        # Walk-in sessions without a case stay on the typed form (no goals to match).
        recording.extraction_status = ExtractionStatus.SKIPPED.value
        db.commit()
        return recording

    recording.extraction_status = ExtractionStatus.RUNNING.value
    db.commit()

    started = time.monotonic()
    try:
        if voice_session_v2_active() or clinical_language_engine_active():
            context = build_session_interpretation_context(
                db,
                recording.case_id,
                session_id=recording.session_id,
            )
        else:
            context = build_case_context(db, recording.case_id)
        extraction = extract_with_cle_if_active(
            recording.transcript,
            context,
            starting_state=None,
        )
        recording.extraction_json = extraction.model_dump_json()
        recording.extraction_status = ExtractionStatus.COMPLETED.value
    except (ValidationError, ValueError, KeyError) as exc:
        logger.warning("Voice extraction returned malformed output for recording %s: %s", recording.id, exc)
        recording.extraction_status = ExtractionStatus.PARTIAL.value
        recording.error_message = "We couldn't structure everything — your transcript is ready to review."
    except Exception as exc:  # noqa: BLE001 — pipeline failures land on the row
        logger.exception("Voice extraction failed for recording %s", recording.id)
        recording.extraction_status = ExtractionStatus.FAILED.value
        recording.error_message = str(exc)[:2000]
    finally:
        elapsed_ms = int((time.monotonic() - started) * 1000)
        recording.processing_ms = (recording.processing_ms or 0) + elapsed_ms
        db.commit()
    return recording
