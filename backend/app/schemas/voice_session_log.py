"""Voice-first session log — strict extraction schema.

The LLM extraction step must return JSON matching VoiceSessionLogExtraction.
Malformed output is rejected safely (therapist proceeds with the typed form).

Design rules (CTO plan):
- Measurement values reuse the existing v2 enums — never invented values.
- Goal/strategy IDs must come from the candidate set supplied in the prompt;
  anything else is stripped and demoted to a candidate label.
- Output maps 1:1 onto the existing session_evidence v2 payload + DailyLog
  fields, so submission uses the unchanged POST /api/v1/daily-logs path.
"""

from __future__ import annotations

import json
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from app.core.clinical_measurement_criteria import validate_measurement_value

EXTRACTION_SCHEMA_VERSION = 1
EXTRACTION_SCHEMA_VERSION_V2 = 2

MatchLabel = Literal["strong_possible_match", "possible_match", "needs_review"]
SourceType = Literal["active_iep", "emerging", "ai_identified"]
InsightCertainty = Literal[
    "single_session_signal",
    "early_pattern",
    "repeated_pattern",
    "insufficient_evidence",
]

PROGRESS_SIGNAL_NOT_STATED = "not_stated"


def compute_match_label(
    goal_card_id: int | None,
    confidence: float,
    *,
    is_emerging: bool = False,
) -> MatchLabel:
    """Workflow guidance labels — not clinical certainty."""
    if is_emerging or not goal_card_id:
        return "needs_review"
    if confidence >= 0.75:
        return "strong_possible_match"
    if confidence >= 0.5:
        return "possible_match"
    return "needs_review"


MATCH_LABEL_DISPLAY = {
    "strong_possible_match": "Strong possible match",
    "possible_match": "Possible match",
    "needs_review": "Needs review",
}


def _clean_measurement(field: str, value: Optional[str]) -> Optional[str]:
    if value in (None, "", PROGRESS_SIGNAL_NOT_STATED):
        return None
    if not validate_measurement_value(field, value):
        return None
    return value


class VoiceGoalEvidence(BaseModel):
    """Evidence extracted for one goal the therapist worked on."""

    goal_card_id: Optional[int] = None
    goal_repository_item_id: Optional[int] = None
    # Set when no existing goal matched — becomes a case-level goal candidate.
    goal_candidate_label: Optional[str] = Field(default=None, max_length=300)
    goal_label: str = Field(..., min_length=1, max_length=300)
    source_type: Optional[SourceType] = None
    match_label: Optional[MatchLabel] = None
    evidence_summary: str = Field(default="", max_length=2000)
    child_response: str = Field(default="", max_length=2000)
    participation: Optional[str] = None
    independence_support_needed: Optional[str] = None
    goal_achievement: Optional[str] = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    source_transcript_excerpt: str = Field(default="", max_length=1000)

    @model_validator(mode="after")
    def _fill_match_label(self) -> "VoiceGoalEvidence":
        if self.match_label is None:
            self.match_label = compute_match_label(
                self.goal_card_id,
                self.confidence,
                is_emerging=bool(self.goal_candidate_label) and not self.goal_card_id,
            )
        if self.source_type is None:
            if self.goal_card_id:
                self.source_type = "active_iep"
            elif self.goal_candidate_label:
                self.source_type = "emerging"
            else:
                self.source_type = "ai_identified"
        return self

    @field_validator("participation")
    @classmethod
    def _v_participation(cls, v: Optional[str]) -> Optional[str]:
        return _clean_measurement("participation", v)

    @field_validator("independence_support_needed")
    @classmethod
    def _v_independence(cls, v: Optional[str]) -> Optional[str]:
        return _clean_measurement("independence_support_needed", v)

    @field_validator("goal_achievement")
    @classmethod
    def _v_achievement(cls, v: Optional[str]) -> Optional[str]:
        return _clean_measurement("goal_achievement", v)


class VoiceStrategyUse(BaseModel):
    """One support strategy mentioned in the recording."""

    strategy_id: Optional[int] = None
    # Set when no existing strategy matched — becomes a case-level candidate.
    strategy_candidate_label: Optional[str] = Field(default=None, max_length=300)
    strategy_label: str = Field(..., min_length=1, max_length=300)
    spoken_phrase: str = Field(default="", max_length=500)
    implementation_summary: str = Field(default="", max_length=2000)
    child_response: str = Field(default="", max_length=2000)
    # Index into goal_evidence for linking; None = session-level strategy.
    goal_index: Optional[int] = Field(default=None, ge=0)
    strategy_feedback: Optional[str] = None
    match_confidence: float = Field(default=0.0, ge=0.0, le=1.0)

    @field_validator("strategy_feedback")
    @classmethod
    def _v_feedback(cls, v: Optional[str]) -> Optional[str]:
        allowed = {"worked_well", "partially_worked", "did_not_work", "not_observed"}
        if v in (None, "", PROGRESS_SIGNAL_NOT_STATED):
            return None
        return v if v in allowed else None


class VoiceSupportSignal(BaseModel):
    label: str = Field(default="", max_length=300)
    support_type: str = Field(default="accommodation", max_length=64)
    linked_goal_index: Optional[int] = Field(default=None, ge=0)
    evidence: str = Field(default="", max_length=1000)
    source_excerpt: str = Field(default="", max_length=500)


class VoiceParticipationSignal(BaseModel):
    signal_id: str = Field(default="", max_length=64)
    label: str = Field(default="", max_length=200)
    evidence: str = Field(default="", max_length=1000)
    source_excerpt: str = Field(default="", max_length=500)


class VoiceStrengthSignal(BaseModel):
    label: str = Field(default="", max_length=200)
    evidence: str = Field(default="", max_length=1000)
    source_excerpt: str = Field(default="", max_length=500)


class VoiceSessionInsight(BaseModel):
    insight_type: str = Field(default="learned_today", max_length=64)
    title: str = Field(default="", max_length=200)
    summary: str = Field(default="", max_length=2000)
    certainty: InsightCertainty = "single_session_signal"


class VoiceFamilySummary(BaseModel):
    worked_on: list[str] = Field(default_factory=list)
    appeared_helpful: list[str] = Field(default_factory=list)
    strength_highlight: list[str] = Field(default_factory=list)
    looking_ahead: list[str] = Field(default_factory=list)


class VoiceExtractionMetadata(BaseModel):
    prompt_version: str = "voice_session_v1"
    model: str = ""
    provider: str = ""
    context_goal_count: int = 0
    context_strategy_count: int = 0
    processed_at: Optional[str] = None


class VoiceSafetyFlag(BaseModel):
    flag_type: str = Field(default="", max_length=64)
    description: str = Field(default="", max_length=500)


class VoiceTherapistReviewMetadata(BaseModel):
    narrative_acceptance: Optional[str] = Field(default=None, max_length=32)
    pending_review_count: int = 0


class VoiceSessionLogExtraction(BaseModel):
    """Full structured output for one session recording."""

    schema_version: int = EXTRACTION_SCHEMA_VERSION
    session_summary: str = Field(default="", max_length=4000)
    session_story: str = Field(default="", max_length=4000)
    goal_evidence: list[VoiceGoalEvidence] = Field(default_factory=list)
    strategies: list[VoiceStrategyUse] = Field(default_factory=list)
    support_signals: list[VoiceSupportSignal] = Field(default_factory=list)
    participation_signals: list[VoiceParticipationSignal] = Field(default_factory=list)
    strengths: list[VoiceStrengthSignal] = Field(default_factory=list)
    child_response_summary: str = Field(default="", max_length=2000)
    progress_summary: str = Field(default="", max_length=2000)
    barriers_or_concerns: str = Field(default="", max_length=2000)
    next_session_plan: str = Field(default="", max_length=2000)
    parent_note_draft: str = Field(default="", max_length=2000)
    internal_note_candidate: str = Field(default="", max_length=2000)
    family_summary: VoiceFamilySummary = Field(default_factory=VoiceFamilySummary)
    session_insights: list[VoiceSessionInsight] = Field(default_factory=list)
    starting_state: Optional[str] = Field(default=None, max_length=64)
    missing_information: list[str] = Field(default_factory=list)
    review_flags: list[str] = Field(default_factory=list)
    safety_flags: list[VoiceSafetyFlag] = Field(default_factory=list)
    extraction_metadata: VoiceExtractionMetadata = Field(default_factory=VoiceExtractionMetadata)
    therapist_review_metadata: VoiceTherapistReviewMetadata = Field(default_factory=VoiceTherapistReviewMetadata)

    @model_validator(mode="after")
    def _sync_story_fields(self) -> "VoiceSessionLogExtraction":
        if self.session_story and not self.session_summary:
            self.session_summary = self.session_story
        elif self.session_summary and not self.session_story:
            self.session_story = self.session_summary
        return self

    def validated_against(
        self,
        *,
        allowed_goal_card_ids: set[int],
        allowed_strategy_ids: set[int],
    ) -> "VoiceSessionLogExtraction":
        """Strip IDs the model was not given — invented IDs become candidates."""
        for goal in self.goal_evidence:
            if goal.goal_card_id is not None and goal.goal_card_id not in allowed_goal_card_ids:
                goal.goal_candidate_label = goal.goal_candidate_label or goal.goal_label
                goal.goal_card_id = None
                goal.goal_repository_item_id = None
        for strat in self.strategies:
            if strat.strategy_id is not None and strat.strategy_id not in allowed_strategy_ids:
                strat.strategy_candidate_label = strat.strategy_candidate_label or strat.strategy_label
                strat.strategy_id = None
        return self

    def to_session_evidence_payload(self) -> dict[str, Any]:
        """Map onto the existing session_evidence v2 payload consumed by
        clinical_evidence_service.save_session_evidence (goals with nested
        strategies). Only confirmed structure — the therapist edits before submit.
        """
        goals: list[dict[str, Any]] = []
        strategies_by_goal: dict[int, list[dict[str, Any]]] = {}
        loose_strategies: list[dict[str, Any]] = []

        for strat in self.strategies:
            item = {
                "schema_version": 2,
                "strategy_id": strat.strategy_id,
                "strategy_label": strat.strategy_label,
                "short_note": strat.implementation_summary or strat.spoken_phrase,
                "outcome_note": strat.child_response,
                "strategy_feedback": strat.strategy_feedback,
            }
            if strat.goal_index is not None and strat.goal_index < len(self.goal_evidence):
                strategies_by_goal.setdefault(strat.goal_index, []).append(item)
            else:
                loose_strategies.append(item)

        for idx, goal in enumerate(self.goal_evidence):
            goals.append(
                {
                    "schema_version": 2,
                    "goal_card_id": goal.goal_card_id,
                    "goal_repository_item_id": goal.goal_repository_item_id,
                    "goal_label": goal.goal_label,
                    "response_note": goal.child_response or goal.evidence_summary,
                    "measurement_note": goal.evidence_summary,
                    "participation": goal.participation,
                    "independence_support_needed": goal.independence_support_needed,
                    "goal_achievement": goal.goal_achievement,
                    "strategies": strategies_by_goal.get(idx, []),
                }
            )

        return {"schema_version": 2, "goals": goals, "strategies": loose_strategies}

    def to_daily_log_fields(self) -> dict[str, str]:
        """Prefill the existing DailyLog prose fields consumed by report compilers."""
        fields: dict[str, str] = {}
        if self.session_summary:
            fields["activities_done"] = self.session_summary
        goal_labels = "; ".join(g.goal_label for g in self.goal_evidence if g.goal_label)
        if goal_labels:
            fields["goals_addressed"] = goal_labels
        observations_parts = [p for p in (self.child_response_summary, self.progress_summary) if p]
        if self.barriers_or_concerns:
            observations_parts.append(f"Barriers/concerns: {self.barriers_or_concerns}")
        if observations_parts:
            fields["observations"] = "\n\n".join(observations_parts)
        if self.next_session_plan:
            fields["follow_ups"] = self.next_session_plan
        if self.parent_note_draft:
            fields["parent_notes"] = self.parent_note_draft
        if self.internal_note_candidate:
            fields["session_notes"] = self.internal_note_candidate
        return fields

    @property
    def new_goal_candidates(self) -> list[VoiceGoalEvidence]:
        return [g for g in self.goal_evidence if g.goal_card_id is None and g.goal_candidate_label]

    @property
    def new_strategy_candidates(self) -> list[VoiceStrategyUse]:
        return [s for s in self.strategies if s.strategy_id is None and s.strategy_candidate_label]

    def to_structured_session_evidence(
        self,
        *,
        session_id: int | None = None,
        recording_id: int | None = None,
        transcript: str = "",
    ) -> "StructuredSessionEvidence":
        from app.schemas.structured_session_evidence import (
            StructuredAiMetadata,
            StructuredGoalEvidence,
            StructuredObservations,
            StructuredParentUpdate,
            StructuredSessionEvidence,
            StructuredStrategyEvidence,
        )

        goals: list[StructuredGoalEvidence] = []
        review_items: list[str] = []
        strategies_by_goal: dict[int, list[StructuredStrategyEvidence]] = {}

        for strat in self.strategies:
            item = StructuredStrategyEvidence(
                strategy_id=strat.strategy_id,
                strategy_label=strat.strategy_label or strat.strategy_candidate_label or "",
                feedback=strat.strategy_feedback,
                confidence=strat.match_confidence,
                spoken_phrase=strat.spoken_phrase or strat.implementation_summary[:500],
            )
            if strat.goal_index is not None and strat.goal_index < len(self.goal_evidence):
                strategies_by_goal.setdefault(strat.goal_index, []).append(item)
            else:
                pass  # session-level handled below

        session_level = [
            StructuredStrategyEvidence(
                strategy_id=s.strategy_id,
                strategy_label=s.strategy_label or s.strategy_candidate_label or "",
                feedback=s.strategy_feedback,
                confidence=s.match_confidence,
                spoken_phrase=s.spoken_phrase or s.implementation_summary[:500],
            )
            for s in self.strategies
            if s.goal_index is None or s.goal_index >= len(self.goal_evidence)
        ]

        matched = 0
        suggested = 0
        for idx, goal in enumerate(self.goal_evidence):
            if goal.goal_card_id:
                match_type = "active_iep"
                matched += 1
            elif goal.goal_candidate_label:
                match_type = "new_observation"
            else:
                match_type = "suggested"
                suggested += 1
            status = "pending"
            if goal.confidence >= 0.85 and goal.goal_card_id:
                status = "pending"
            if goal.confidence < 0.6:
                review_items.append(f"goal:{goal.goal_card_id or idx}:low_confidence")
            progress: list[str] = []
            if goal.participation:
                progress.append(goal.participation)
            if goal.goal_achievement:
                progress.append(goal.goal_achievement)
            evidence_bits: list[str] = []
            if goal.evidence_summary:
                evidence_bits.append(goal.evidence_summary[:200])
            if goal.child_response:
                evidence_bits.append(goal.child_response[:200])
            goals.append(
                StructuredGoalEvidence(
                    goal_id=goal.goal_card_id,
                    goal_card_id=goal.goal_card_id,
                    goal_repository_item_id=goal.goal_repository_item_id,
                    goal_label=goal.goal_label or goal.goal_candidate_label or "",
                    match_type=match_type,
                    confidence=goal.confidence,
                    status=status,
                    source_transcript_excerpt=goal.source_transcript_excerpt or goal.evidence_summary[:500],
                    strategies=strategies_by_goal.get(idx, []),
                    progress=progress,
                    evidence=evidence_bits,
                    participation=goal.participation,
                    independence_support_needed=goal.independence_support_needed,
                    goal_achievement=goal.goal_achievement,
                )
            )
        for flag in self.review_flags:
            if flag not in review_items:
                review_items.append(flag)

        parent_bullets = []
        if self.family_summary.worked_on:
            parent_bullets = self.family_summary.worked_on[:5]
        elif self.parent_note_draft:
            parent_bullets = [line.strip() for line in self.parent_note_draft.replace("•", "\n").split("\n") if line.strip()]

        wins: list[str] = []
        if self.progress_summary:
            wins = [self.progress_summary[:300]]
        strengths: list[str] = []
        if self.strengths:
            strengths = [s.label for s in self.strengths if s.label][:5]
        elif self.child_response_summary:
            strengths = [self.child_response_summary[:300]]

        avg_conf = sum(g.confidence for g in goals) / len(goals) if goals else 0.0

        return StructuredSessionEvidence(
            session_id=session_id,
            recording_id=recording_id,
            voice_transcript=transcript,
            todays_story=self.session_story or self.session_summary or transcript[:2000],
            goals=goals,
            strategies_session_level=session_level,
            observations=StructuredObservations(
                strengths=strengths,
                support_needs=[],
                environment_factors=[],
                participation_patterns=[],
            ),
            parent_update=StructuredParentUpdate(
                todays_session=parent_bullets[:5] or ([self.session_summary[:200]] if self.session_summary else []),
                wins_today=wins,
                helpful_supports=[s.strategy_label for s in self.strategies[:3] if s.strategy_label],
                next_session=[self.next_session_plan[:300]] if self.next_session_plan else [],
            ),
            clinical_summary=self.internal_note_candidate or self.session_summary[:2000],
            parent_summary=self.parent_note_draft or self.session_summary[:2000],
            therapist_reflection=None,
            ai_metadata=StructuredAiMetadata(
                matched_goal_count=matched,
                suggested_goal_count=suggested,
                review_items=review_items,
                extraction_confidence=round(avg_conf, 2),
            ),
        )


def parse_extraction_output(raw: Any) -> VoiceSessionLogExtraction:
    """Validate raw model output; raises pydantic.ValidationError on bad shape."""
    if isinstance(raw, str):
        raw = json.loads(raw)
    return VoiceSessionLogExtraction.model_validate(raw)
