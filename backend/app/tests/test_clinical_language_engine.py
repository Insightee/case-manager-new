"""Clinical Language Engine + Voice Session V2 extraction schema tests."""

from __future__ import annotations

import pytest

from app.core.config import settings
from app.schemas.voice_session_log import (
    EXTRACTION_SCHEMA_VERSION_V2,
    VoiceSessionLogExtraction,
    compute_match_label,
    parse_extraction_output,
)
from app.services.clinical_language_engine_service import interpret_session_structure
from app.services.insights.helpers import contains_banned_language
from app.services.session_context_builder import _deterministic_evidence_gaps


@pytest.fixture
def cle_flags(monkeypatch):
    monkeypatch.setattr(settings, "enable_voice_session_v2", True)
    monkeypatch.setattr(settings, "enable_clinical_language_engine", True)
    monkeypatch.setattr(settings, "AI_ENABLED", False)


def test_compute_match_label_tiers():
    assert compute_match_label(1, 0.8) == "strong_possible_match"
    assert compute_match_label(1, 0.6) == "possible_match"
    assert compute_match_label(1, 0.3) == "needs_review"
    assert compute_match_label(None, 0.9, is_emerging=True) == "needs_review"


def test_v2_schema_parses_extended_fields():
    raw = {
        "schema_version": EXTRACTION_SCHEMA_VERSION_V2,
        "session_summary": "Participated with visual support.",
        "session_story": "Participated with visual support.",
        "goal_evidence": [
            {
                "goal_card_id": 1,
                "goal_label": "Transition routines",
                "confidence": 0.82,
            }
        ],
        "support_signals": [{"label": "Visual countdown", "support_type": "accommodation"}],
        "participation_signals": [{"signal_id": "engaged", "label": "Engaged with activity"}],
        "strengths": [{"label": "Requested a break"}],
        "family_summary": {"worked_on": ["Transitions"], "looking_ahead": ["Continue visuals"]},
        "session_insights": [
            {
                "insight_type": "learned_today",
                "title": "Snapshot",
                "summary": "Visual prep noted.",
                "certainty": "single_session_signal",
            }
        ],
        "extraction_metadata": {"prompt_version": "voice_session_v2", "provider": "mock"},
    }
    ext = parse_extraction_output(raw)
    assert ext.schema_version == EXTRACTION_SCHEMA_VERSION_V2
    assert ext.goal_evidence[0].match_label == "strong_possible_match"
    assert ext.support_signals[0].label == "Visual countdown"
    assert ext.family_summary.worked_on == ["Transitions"]


def test_cle_mock_extraction_neuro_affirming(cle_flags):
    context = {
        "goals": [{"goal_card_id": 10, "label": "Communication", "domain_key": "comm"}],
        "strategies": [{"strategy_id": 5, "label": "Visual schedule", "linked_goal_card_id": 10, "scope": "case"}],
        "recent_confirmed_sessions": [],
        "evidence_gaps": [],
    }
    transcript = (
        "Today we worked on communication. The child participated with support "
        "and requested a break before returning to the activity."
    )
    ext = interpret_session_structure(transcript, context)
    assert ext.schema_version == EXTRACTION_SCHEMA_VERSION_V2
    assert ext.session_story
    assert ext.extraction_metadata.prompt_version
    assert ext.extraction_metadata.provider == "mock"
    for goal in ext.goal_evidence:
        assert goal.match_label in ("strong_possible_match", "possible_match", "needs_review")
    assert not contains_banned_language(ext.session_story)


def test_cle_flags_banned_language_in_review(cle_flags):
    raw = VoiceSessionLogExtraction(
        schema_version=EXTRACTION_SCHEMA_VERSION_V2,
        session_summary="The patient showed non-compliant behavior and deficit in attention.",
        session_story="The patient showed non-compliant behavior and deficit in attention.",
    )
    from app.services.clinical_language_engine_service import _sanitize_banned_language

    flagged = _sanitize_banned_language(raw)
    assert "banned_language_detected" in flagged.review_flags


def test_evidence_gaps_when_goal_not_recently_documented():
    from app.services.session_context_builder import _deterministic_evidence_gaps

    gaps = _deterministic_evidence_gaps(
        {"goals": [{"label": "Transition routines"}]},
        [],
    )
    assert any("Transition" in g for g in gaps)
    assert any("No prior structured" in g for g in gaps)
