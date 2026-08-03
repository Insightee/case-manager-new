"""Structured session evidence — canonical voice-first session log storage.

Therapists confirm structured chips and entities; prose DailyLog fields are
derived at submit for legacy report paths.
"""

from __future__ import annotations

import json
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

STRUCTURED_SESSION_SCHEMA_VERSION = 1

GoalMatchType = Literal["active_iep", "suggested", "new_observation"]
GoalConfirmStatus = Literal["pending", "confirmed", "rejected", "changed"]


class StructuredStrategyEvidence(BaseModel):
    strategy_id: Optional[int] = None
    strategy_label: str = Field(default="", max_length=300)
    feedback: Optional[str] = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    spoken_phrase: str = Field(default="", max_length=500)
    child_response_note: Optional[str] = Field(default=None, max_length=400)


class StructuredGoalEvidence(BaseModel):
    goal_id: Optional[int] = None
    goal_card_id: Optional[int] = None
    goal_repository_item_id: Optional[int] = None
    goal_label: str = Field(default="", max_length=300)
    match_type: GoalMatchType = "active_iep"
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    status: GoalConfirmStatus = "pending"
    source_transcript_excerpt: str = Field(default="", max_length=1000)
    strategies: list[StructuredStrategyEvidence] = Field(default_factory=list)
    progress: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    participation: Optional[str] = None
    independence_support_needed: Optional[str] = None
    goal_achievement: Optional[str] = None
    # Emerging-goal candidate lifecycle (match_type == "new_observation")
    therapist_note: Optional[str] = Field(default=None, max_length=500)
    candidate_id: Optional[int] = None
    candidate_status: Optional[str] = None


class StructuredObservations(BaseModel):
    strengths: list[str] = Field(default_factory=list)
    support_needs: list[str] = Field(default_factory=list)
    environment_factors: list[str] = Field(default_factory=list)
    participation_patterns: list[str] = Field(default_factory=list)


class StructuredParentUpdate(BaseModel):
    todays_session: list[str] = Field(default_factory=list)
    wins_today: list[str] = Field(default_factory=list)
    helpful_supports: list[str] = Field(default_factory=list)
    next_session: list[str] = Field(default_factory=list)


class StructuredChallengeObservation(BaseModel):
    text: str = Field(default="", max_length=800)
    source: Optional[str] = None  # 'ai' | 'therapist'
    flag_cm_review: bool = False
    incident_reported: bool = False


class StructuredCandidateRef(BaseModel):
    """Reference to a goal/strategy candidate sent to CM review."""

    candidate_id: Optional[int] = None
    label: str = Field(default="", max_length=300)
    status: Optional[str] = None


class StructuredSessionContext(BaseModel):
    environment: Optional[str] = Field(default=None, max_length=64)
    service_type: Optional[str] = Field(default=None, max_length=64)


class StructuredAiMetadata(BaseModel):
    matched_goal_count: int = 0
    suggested_goal_count: int = 0
    rejected_matches: list[str] = Field(default_factory=list)
    new_strategies: list[str] = Field(default_factory=list)
    review_items: list[str] = Field(default_factory=list)
    extraction_confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class StructuredSessionEvidence(BaseModel):
    schema_version: int = STRUCTURED_SESSION_SCHEMA_VERSION
    session_id: Optional[int] = None
    recording_id: Optional[int] = None
    voice_transcript: str = Field(default="", max_length=16000)
    todays_story: str = Field(default="", max_length=4000)
    story_edited_by_therapist: bool = False
    goals: list[StructuredGoalEvidence] = Field(default_factory=list)
    strategies_session_level: list[StructuredStrategyEvidence] = Field(default_factory=list)
    child_response_signals: list[str] = Field(default_factory=list)
    challenge_observations: list[StructuredChallengeObservation] = Field(default_factory=list)
    goal_candidates: list[StructuredCandidateRef] = Field(default_factory=list)
    strategy_candidates: list[StructuredCandidateRef] = Field(default_factory=list)
    session_context: StructuredSessionContext = Field(default_factory=StructuredSessionContext)
    no_goal_reason: Optional[str] = Field(default=None, max_length=64)
    extraction_version: Optional[int] = None
    dismissed_recommendations: list[str] = Field(default_factory=list)
    next_session_strategy_notes: list[str] = Field(default_factory=list)
    observations: StructuredObservations = Field(default_factory=StructuredObservations)
    parent_update: StructuredParentUpdate = Field(default_factory=StructuredParentUpdate)
    clinical_summary: str = Field(default="", max_length=4000)
    parent_summary: str = Field(default="", max_length=4000)
    therapist_reflection: Optional[str] = Field(default=None, max_length=500)
    ai_metadata: StructuredAiMetadata = Field(default_factory=StructuredAiMetadata)

    def confirmed_goals(self) -> list[StructuredGoalEvidence]:
        return [g for g in self.goals if g.status in ("confirmed", "changed")]

    @staticmethod
    def _normalize_strategy_feedback_for_evidence(feedback: Optional[str]) -> Optional[str]:
        """Map voice-session vocabulary to clinical evidence enums."""
        if not feedback:
            return None
        voice_map = {
            "worked_well": "HELPFUL",
            "partially_worked": "PARTLY_HELPFUL",
            "did_not_work": "NOT_HELPFUL",
            "not_observed": None,
        }
        key = feedback.strip().lower()
        if key in voice_map:
            return voice_map[key]
        upper = feedback.strip().upper()
        allowed = {"HELPFUL", "PARTLY_HELPFUL", "NOT_HELPFUL", "CHILD_REJECTED", "NEEDS_ADAPTATION"}
        return upper if upper in allowed else None

    def pending_review_count(self) -> int:
        return sum(1 for g in self.goals if g.status == "pending")

    def to_session_evidence_payload(self) -> dict[str, Any]:
        """Map confirmed goals onto session_evidence v2 for clinical_evidence_service."""
        goals: list[dict[str, Any]] = []
        loose: list[dict[str, Any]] = []
        for goal in self.confirmed_goals():
            strat_rows = []
            for s in goal.strategies:
                if not s.strategy_label:
                    continue
                strat_rows.append(
                    {
                        "schema_version": 2,
                        "strategy_id": s.strategy_id,
                        "strategy_label": s.strategy_label,
                        "short_note": s.spoken_phrase or s.strategy_label,
                        "strategy_feedback": StructuredSessionEvidence._normalize_strategy_feedback_for_evidence(
                            s.feedback
                        ),
                    }
                )
            goals.append(
                {
                    "schema_version": 2,
                    "goal_card_id": goal.goal_card_id,
                    "goal_repository_item_id": goal.goal_repository_item_id,
                    "goal_label": goal.goal_label,
                    "measurement_note": " · ".join(goal.evidence[:3]) if goal.evidence else "",
                    "response_note": goal.source_transcript_excerpt or "",
                    "participation": goal.participation,
                    "independence_support_needed": goal.independence_support_needed,
                    "goal_achievement": goal.goal_achievement,
                    "strategies": strat_rows,
                }
            )
        for s in self.strategies_session_level:
            if not s.strategy_label:
                continue
            loose.append(
                {
                    "schema_version": 2,
                    "strategy_id": s.strategy_id,
                    "strategy_label": s.strategy_label,
                    "short_note": s.spoken_phrase or s.strategy_label,
                    "strategy_feedback": StructuredSessionEvidence._normalize_strategy_feedback_for_evidence(
                        s.feedback
                    ),
                }
            )
        return {"schema_version": 2, "goals": goals, "strategies": loose}

    def to_daily_log_fields(self) -> dict[str, str]:
        """Derive legacy prose fields — not therapist-authored."""
        fields: dict[str, str] = {}
        if self.todays_story:
            fields["activities_done"] = self.todays_story
        labels = [g.goal_label for g in self.confirmed_goals() if g.goal_label]
        if labels:
            fields["goals_addressed"] = "; ".join(labels)
        obs_parts: list[str] = []
        for key in ("strengths", "support_needs", "environment_factors", "participation_patterns"):
            items = getattr(self.observations, key, [])
            if items:
                obs_parts.append(f"{key.replace('_', ' ').title()}: {', '.join(items)}")
        if self.child_response_signals:
            obs_parts.append(
                "Child response: " + ", ".join(s.replace("_", " ") for s in self.child_response_signals)
            )
        challenge_lines = [c.text for c in self.challenge_observations if c.text.strip()]
        if challenge_lines:
            obs_parts.append("Challenges/concerns: " + " | ".join(challenge_lines))
        if self.no_goal_reason:
            obs_parts.append(f"No IEP goal addressed — reason: {self.no_goal_reason.replace('_', ' ')}")
        if obs_parts:
            fields["observations"] = "\n\n".join(obs_parts)
        if self.parent_update.next_session:
            fields["follow_ups"] = "\n".join(f"• {b}" for b in self.parent_update.next_session)
        if self.parent_summary:
            fields["parent_notes"] = self.parent_summary
        elif self.parent_update.todays_session:
            fields["parent_notes"] = "\n".join(f"• {b}" for b in self.parent_update.todays_session)
        if self.clinical_summary:
            fields["session_notes"] = self.clinical_summary
        return fields

    def to_json_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


def parse_structured_session(raw: Any) -> StructuredSessionEvidence:
    if isinstance(raw, str):
        raw = json.loads(raw)
    return StructuredSessionEvidence.model_validate(raw)
