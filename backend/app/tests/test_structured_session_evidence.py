"""Tests for structured session evidence mapping."""

from app.schemas.structured_session_evidence import StructuredSessionEvidence, parse_structured_session
from app.schemas.voice_session_log import VoiceSessionLogExtraction, VoiceGoalEvidence


def test_extraction_to_structured_session_evidence():
    extraction = VoiceSessionLogExtraction(
        session_summary="We had a calm session working on transitions.",
        goal_evidence=[
            VoiceGoalEvidence(
                goal_card_id=1,
                goal_label="Social interaction",
                evidence_summary="Initiated with a peer once.",
                confidence=0.91,
                source_transcript_excerpt="she waved at her friend",
            )
        ],
        parent_note_draft="Today we practiced social greetings.",
    )
    structured = extraction.to_structured_session_evidence(
        session_id=10,
        recording_id=20,
        transcript="she waved at her friend during circle time",
    )
    assert structured.session_id == 10
    assert structured.recording_id == 20
    assert len(structured.goals) == 1
    assert structured.goals[0].goal_card_id == 1
    assert structured.goals[0].status == "pending"
    assert structured.todays_story.startswith("We had a calm")
    payload = structured.to_session_evidence_payload()
    assert payload["schema_version"] == 2


def test_structured_session_roundtrip_json():
    raw = {
        "schema_version": 1,
        "session_id": 5,
        "todays_story": "Story",
        "goals": [],
        "observations": {"strengths": ["Calm"], "support_needs": [], "environment_factors": [], "participation_patterns": []},
        "parent_update": {"todays_session": ["Worked on goals"], "wins_today": [], "helpful_supports": [], "next_session": []},
    }
    model = parse_structured_session(raw)
    assert isinstance(model, StructuredSessionEvidence)
    assert model.parent_update.todays_session == ["Worked on goals"]


def test_structured_session_v1_extended_fields_roundtrip():
    """New voice-first V1 fields survive parse → dump (not dropped by pydantic)."""
    raw = {
        "schema_version": 1,
        "session_id": 7,
        "todays_story": "Regulation-focused day",
        "story_edited_by_therapist": True,
        "goals": [
            {
                "goal_label": "Turn-taking in play",
                "match_type": "new_observation",
                "status": "pending",
                "therapist_note": "Seen twice this week",
                "candidate_id": 42,
                "candidate_status": "pending_review",
            }
        ],
        "child_response_signals": ["requested_break", "returned_after_regulation"],
        "challenge_observations": [
            {"text": "Loud hallway made transitions harder", "source": "ai", "flag_cm_review": True}
        ],
        "goal_candidates": [{"candidate_id": 42, "label": "Turn-taking in play", "status": "pending_review"}],
        "strategy_candidates": [{"label": "Quiet corner access", "status": "pending_review"}],
        "session_context": {"environment": "school", "service_type": "shadow_support"},
        "no_goal_reason": "regulation_day",
        "extraction_version": 1,
    }
    model = parse_structured_session(raw)
    dumped = model.to_json_dict()
    assert dumped["story_edited_by_therapist"] is True
    assert dumped["child_response_signals"] == ["requested_break", "returned_after_regulation"]
    assert dumped["challenge_observations"][0]["flag_cm_review"] is True
    assert dumped["goal_candidates"][0]["candidate_id"] == 42
    assert dumped["strategy_candidates"][0]["label"] == "Quiet corner access"
    assert dumped["session_context"]["environment"] == "school"
    assert dumped["no_goal_reason"] == "regulation_day"
    assert dumped["extraction_version"] == 1
    assert dumped["goals"][0]["candidate_status"] == "pending_review"

    # Challenges + signals + no-goal reason fold into derived observations prose.
    fields = model.to_daily_log_fields()
    assert "Challenges/concerns" in fields["observations"]
    assert "Child response" in fields["observations"]
    assert "regulation day" in fields["observations"]
    # Emerging goals never become confirmed evidence.
    assert model.to_session_evidence_payload()["goals"] == []
