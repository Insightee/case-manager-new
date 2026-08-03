"""Clinical Language Engine — versioned neuro-affirmative session interpretation.

Voice Session Log V2 extraction path. AI condenses therapist speech into
structured candidates; it does not create clinical truth.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from app.core.clinical_measurement_criteria import (
    GOAL_ACHIEVEMENT_VALUES,
    INDEPENDENCE_VALUES,
    PARTICIPATION_VALUES,
)
from app.core.config import settings
from app.core.feature_flags import clinical_language_engine_active
from app.schemas.voice_session_log import (
    EXTRACTION_SCHEMA_VERSION_V2,
    VoiceSessionLogExtraction,
    compute_match_label,
    parse_extraction_output,
)
from app.services.insights.helpers import BANNED_WORDS, contains_banned_language
from app.services.session_log_extraction_service import (
    MAX_TRANSCRIPT_CHARS,
    _call_openai_extraction,
    _extraction_provider,
    _mock_extraction,
    match_strategy_label,
)

logger = logging.getLogger("insightcase")

PROMPT_VERSION = settings.session_interpretation_prompt_version

CLE_SYSTEM_PROMPT = """You interpret a therapist's spoken session update into structured clinical evidence.
Rules — follow all strictly:
- Use ONLY goal_card_id and strategy_id from the candidate lists. Never invent IDs.
- Unmatched goals/strategies: set id null and fill goal_candidate_label / strategy_candidate_label.
- Never invent session events not described in the transcript. Return null/empty when unsure.
- Never diagnose. Never infer trauma, attachment, or internal states from isolated language.
- Never equate participation with compliance. Never frame accommodation use negatively.
- Use neuro-affirming, participation-focused language. Avoid: {banned_sample}.
- participation: {participation}. independence_support_needed: {independence}. goal_achievement: {achievement}.
- strategy_feedback: worked_well, partially_worked, did_not_work, not_observed — or omit.
- Distinguish strategies (therapist actions) from support_signals (accommodations/environment).
- participation_signals: use ids engaged, participated_with_support, initiated_interaction, requested_break,
  needed_extra_time, declined_activity, became_overwhelmed, returned_after_regulation, self_advocated,
  explored_independently, not_clearly_observed.
- parent_note_draft / family_summary: warm, observable, parent-safe — no internal detail.
- session_insights: cautious, evidence-limited; certainty one of single_session_signal, early_pattern,
  repeated_pattern, insufficient_evidence.
- schema_version must be {schema_version}.
Return ONLY valid JSON matching the schema hint."""


def _v2_schema_hint(starting_state: Optional[str]) -> dict[str, Any]:
    return {
        "schema_version": EXTRACTION_SCHEMA_VERSION_V2,
        "session_summary": "",
        "session_story": "",
        "goal_evidence": [
            {
                "goal_card_id": None,
                "goal_candidate_label": None,
                "goal_label": "",
                "source_type": "active_iep",
                "match_label": "needs_review",
                "evidence_summary": "",
                "child_response": "",
                "participation": None,
                "independence_support_needed": None,
                "goal_achievement": None,
                "confidence": 0.0,
                "source_transcript_excerpt": "",
            }
        ],
        "strategies": [],
        "support_signals": [{"label": "", "support_type": "accommodation", "evidence": ""}],
        "participation_signals": [{"signal_id": "engaged", "label": "", "evidence": ""}],
        "strengths": [{"label": "", "evidence": ""}],
        "child_response_summary": "",
        "progress_summary": "",
        "barriers_or_concerns": "",
        "next_session_plan": "",
        "parent_note_draft": "",
        "internal_note_candidate": "",
        "family_summary": {
            "worked_on": [],
            "appeared_helpful": [],
            "strength_highlight": [],
            "looking_ahead": [],
        },
        "session_insights": [
            {
                "insight_type": "learned_today",
                "title": "",
                "summary": "",
                "certainty": "single_session_signal",
            }
        ],
        "starting_state": starting_state,
        "missing_information": [],
        "review_flags": [],
        "safety_flags": [],
        "extraction_metadata": {
            "prompt_version": PROMPT_VERSION,
            "model": "",
            "provider": "",
        },
        "therapist_review_metadata": {"pending_review_count": 0},
    }


def _cle_user_prompt(transcript: str, context: dict[str, Any], starting_state: Optional[str]) -> str:
    compact = {
        "goals": context.get("goals", [])[:12],
        "strategies": context.get("strategies", [])[:15],
        "environment": context.get("environment"),
        "recent_confirmed_sessions": context.get("recent_confirmed_sessions", [])[:5],
        "evidence_gaps": context.get("evidence_gaps", [])[:6],
        "parent_priorities": context.get("parent_priorities", [])[:4],
    }
    return (
        f"Interpretation context: {json.dumps(compact, separators=(',', ':'))}\n"
        f"Child starting state: {starting_state or 'not recorded'}\n\n"
        f"Transcript:\n{transcript[:MAX_TRANSCRIPT_CHARS]}\n\n"
        f"JSON schema:\n{json.dumps(_v2_schema_hint(starting_state))}"
    )


def _mock_v2_extraction(
    transcript: str,
    context: dict[str, Any],
    starting_state: Optional[str],
) -> dict[str, Any]:
    base = _mock_extraction(transcript, context, starting_state)
    base["schema_version"] = EXTRACTION_SCHEMA_VERSION_V2
    base["session_story"] = base.get("session_summary", "")
    goals = base.get("goal_evidence") or []
    for goal in goals:
        goal["source_type"] = "active_iep" if goal.get("goal_card_id") else "ai_identified"
        goal["match_label"] = compute_match_label(
            goal.get("goal_card_id"),
            float(goal.get("confidence") or 0),
            is_emerging=bool(goal.get("goal_candidate_label")),
        )
    strategies = context.get("strategies") or []
    matched = match_strategy_label(transcript, strategies)
    support_signals: list[dict[str, Any]] = []
    if matched:
        support_signals.append(
            {
                "label": matched.get("label", ""),
                "support_type": "accommodation",
                "evidence": "Mentioned during session",
            }
        )
    participation: list[dict[str, Any]] = []
    lower = transcript.lower()
    if "break" in lower:
        participation.append({"signal_id": "requested_break", "label": "Requested a break", "evidence": ""})
    if "engag" in lower or "particip" in lower:
        participation.append(
            {"signal_id": "participated_with_support", "label": "Participated with support", "evidence": ""}
        )
    strengths: list[dict[str, Any]] = []
    if base.get("child_response_summary"):
        strengths.append({"label": "Communicated during session", "evidence": base["child_response_summary"][:200]})
    summary = base.get("session_summary", "")[:200]
    base.update(
        {
            "support_signals": support_signals,
            "participation_signals": participation,
            "strengths": strengths,
            "family_summary": {
                "worked_on": [summary] if summary else [],
                "appeared_helpful": [s.get("strategy_label", "") for s in base.get("strategies", [])[:2]],
                "strength_highlight": [s.get("label", "") for s in strengths[:1]],
                "looking_ahead": [base.get("next_session_plan", "")[:200]] if base.get("next_session_plan") else [],
            },
            "session_insights": [
                {
                    "insight_type": "learned_today",
                    "title": "Session snapshot",
                    "summary": summary or "Review the draft narrative and confirm evidence.",
                    "certainty": "single_session_signal",
                },
                {
                    "insight_type": "limitation",
                    "title": "Evidence scope",
                    "summary": "Insights reflect this session only until you confirm items.",
                    "certainty": "insufficient_evidence",
                },
            ],
            "safety_flags": [],
            "extraction_metadata": {
                "prompt_version": PROMPT_VERSION,
                "model": "mock-v1",
                "provider": "mock",
                "context_goal_count": len(context.get("goals") or []),
                "context_strategy_count": len(context.get("strategies") or []),
            },
            "therapist_review_metadata": {"pending_review_count": len(goals)},
        }
    )
    return base


def _sanitize_banned_language(extraction: VoiceSessionLogExtraction) -> VoiceSessionLogExtraction:
    """Strip or flag text that violates neuro-affirmative language rules."""
    text_fields = [
        extraction.session_summary,
        extraction.session_story,
        extraction.child_response_summary,
        extraction.progress_summary,
        extraction.barriers_or_concerns,
        extraction.parent_note_draft,
        extraction.internal_note_candidate,
    ]
    for goal in extraction.goal_evidence:
        text_fields.extend([goal.evidence_summary, goal.child_response, goal.goal_label])
    flagged = False
    for text in text_fields:
        if contains_banned_language(text):
            flagged = True
            break
    if flagged and "banned_language_detected" not in extraction.review_flags:
        extraction.review_flags.append("banned_language_detected")
    return extraction


def _apply_v2_post_processing(extraction: VoiceSessionLogExtraction) -> VoiceSessionLogExtraction:
    if not extraction.session_story and extraction.session_summary:
        extraction.session_story = extraction.session_summary
    if not extraction.session_summary and extraction.session_story:
        extraction.session_summary = extraction.session_story
    pending = 0
    for goal in extraction.goal_evidence:
        if goal.match_label is None:
            goal.match_label = compute_match_label(
                goal.goal_card_id,
                goal.confidence,
                is_emerging=bool(goal.goal_candidate_label) and not goal.goal_card_id,
            )
        if goal.source_type is None:
            if goal.goal_card_id:
                goal.source_type = "active_iep"
            elif goal.goal_candidate_label:
                goal.source_type = "emerging"
            else:
                goal.source_type = "ai_identified"
        pending += 1
    extraction.therapist_review_metadata.pending_review_count = pending
    if extraction.extraction_metadata.prompt_version in (None, ""):
        extraction.extraction_metadata.prompt_version = PROMPT_VERSION
    extraction.extraction_metadata.processed_at = datetime.now(timezone.utc).isoformat()
    return _sanitize_banned_language(extraction)


def interpret_session_structure(
    transcript: str,
    context: dict[str, Any],
    *,
    starting_state: Optional[str] = None,
) -> VoiceSessionLogExtraction:
    """Run Clinical Language Engine extraction → validated VoiceSessionLogExtraction v2."""
    provider = _extraction_provider()
    model = settings.session_interpretation_model or settings.SESSION_LOG_MODEL or settings.AI_DEFAULT_MODEL

    if provider == "openai":
        system = CLE_SYSTEM_PROMPT.format(
            banned_sample=", ".join(BANNED_WORDS[:6]),
            participation=", ".join(PARTICIPATION_VALUES),
            independence=", ".join(INDEPENDENCE_VALUES),
            achievement=", ".join(GOAL_ACHIEVEMENT_VALUES),
            schema_version=EXTRACTION_SCHEMA_VERSION_V2,
        )
        raw = _call_openai_extraction(system, _cle_user_prompt(transcript, context, starting_state))
    else:
        raw = _mock_v2_extraction(transcript, context, starting_state)

    raw["schema_version"] = EXTRACTION_SCHEMA_VERSION_V2
    if "extraction_metadata" not in raw:
        raw["extraction_metadata"] = {}
    raw["extraction_metadata"].update(
        {
            "prompt_version": PROMPT_VERSION,
            "model": model,
            "provider": provider,
            "context_goal_count": len(context.get("goals") or []),
            "context_strategy_count": len(context.get("strategies") or []),
        }
    )

    extraction = parse_extraction_output(raw)
    allowed_goal_ids = {g["goal_card_id"] for g in context.get("goals", [])}
    allowed_strategy_ids = {s["strategy_id"] for s in context.get("strategies", [])}
    extraction = extraction.validated_against(
        allowed_goal_card_ids=allowed_goal_ids,
        allowed_strategy_ids=allowed_strategy_ids,
    )
    return _apply_v2_post_processing(extraction)


def extract_with_cle_if_active(
    transcript: str,
    context: dict[str, Any],
    *,
    starting_state: Optional[str] = None,
) -> VoiceSessionLogExtraction:
    """Route to CLE when flag active, else legacy v1 extractor."""
    from app.services.session_log_extraction_service import extract_session_log_structure

    if clinical_language_engine_active():
        return interpret_session_structure(transcript, context, starting_state=starting_state)
    return extract_session_log_structure(transcript, context, starting_state=starting_state)
