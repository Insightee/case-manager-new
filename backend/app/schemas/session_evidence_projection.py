"""Stable read contract for session evidence — consumed by legacy and engine report paths."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class GoalEvidenceProjection(BaseModel):
    goal_card_id: Optional[int] = None
    goal_label: str = ""
    evidence_notes: list[str] = Field(default_factory=list)
    participation: Optional[str] = None
    goal_achievement: Optional[str] = None
    strategies: list[str] = Field(default_factory=list)


class StrategyUseProjection(BaseModel):
    strategy_id: Optional[int] = None
    strategy_label: str = ""
    feedback: Optional[str] = None
    short_note: Optional[str] = None
    goal_label: Optional[str] = None


class SessionEvidenceProjection(BaseModel):
    session_id: int
    case_id: int
    daily_log_id: int
    submitted_at: Optional[datetime] = None
    session_story: str = ""
    confirmed_goal_evidence: list[GoalEvidenceProjection] = Field(default_factory=list)
    confirmed_strategy_uses: list[StrategyUseProjection] = Field(default_factory=list)
    child_response_signals: list[str] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    challenges: list[str] = Field(default_factory=list)
    therapist_reflection: Optional[str] = None
    parent_safe_summary: str = ""
    cm_review_flags: list[str] = Field(default_factory=list)
    source_recording_id: Optional[int] = None
    extraction_version: Optional[int] = None

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")
