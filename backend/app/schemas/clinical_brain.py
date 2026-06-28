"""Pydantic models for Clinical Brain bank/pool/review APIs."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class LanguageCheckRequest(BaseModel):
    text: str = Field(min_length=1)
    context: Optional[str] = None


class LanguageCheckResponse(BaseModel):
    flagged_phrases: list[str]
    compliance_goal_hits: list[str]
    suggested_replacements: dict[str, str]
    severity: str
    safe_to_publish: bool
    requires_clinical_review: bool
    recommendation: Optional[str] = None


class StrategyPoolCreate(BaseModel):
    label: str = Field(min_length=3, max_length=255)
    domain_key: str
    when_to_use: Optional[str] = None
    how_to_use: Optional[str] = None
    avoid: Optional[str] = None
    strategy_steps: Optional[list[str]] = None
    environment_context: Optional[str] = None
    core_domains: Optional[list[str]] = None
    core_environments: Optional[list[str]] = None
    metadata: Optional[dict[str, Any]] = None
    activate: bool = False


class StrategyPoolPatch(BaseModel):
    label: Optional[str] = None
    when_to_use: Optional[str] = None
    how_to_use: Optional[str] = None
    avoid: Optional[str] = None
    domain_key: Optional[str] = None
    environment_context: Optional[str] = None
    strategy_steps: Optional[list[str]] = None
    status: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None


class StrategyPoolMerge(BaseModel):
    canonical_id: int


class ReviewQueueAction(BaseModel):
    action: str = Field(
        pattern="^(approve_case|approve_pool|approve_for_case|send_to_bank|request_edits|return_with_comment|reject|merge)$"
    )
    note: Optional[str] = None
    case_id: Optional[int] = None
    merged_into_id: Optional[int] = None


class GoalCandidatePatch(BaseModel):
    action: Optional[str] = Field(default=None, pattern="^(save_draft|submit_for_cm_review|archive)$")
    label: Optional[str] = None
    goal_statement: Optional[str] = None
    rationale: Optional[str] = None
    domain_key: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None


class StrategyCandidatePatch(BaseModel):
    action: Optional[str] = Field(default=None, pattern="^(save_draft|submit_for_cm_review|archive)$")
    label: Optional[str] = None
    when_to_use: Optional[str] = None
    how_to_use: Optional[str] = None
    avoid: Optional[str] = None
    domain_key: Optional[str] = None
    environment_context: Optional[str] = None
    strategy_steps: Optional[list[str]] = None
    linked_goal_card_id: Optional[int] = None
    metadata: Optional[dict[str, Any]] = None


class StrategyRecommendationFeedbackCreate(BaseModel):
    goal_repository_item_id: Optional[int] = None
    goal_card_id: Optional[int] = None
    strategy_repository_item_id: Optional[int] = None
    recommendation_source: str = "library_match"
    feedback_status: str
    adaptation_text: Optional[str] = None
    dismissal_reason: Optional[str] = None
    source_context: Optional[dict[str, Any]] = None


class StrategyRecommendationFeedbackPatch(BaseModel):
    feedback_status: Optional[str] = None
    adaptation_text: Optional[str] = None
    dismissal_reason: Optional[str] = None


class UnifiedReviewQueueAction(BaseModel):
    action: str = Field(pattern="^(approve|merge|request_revision|mark_case_specific|reject|close)$")
    reviewer_note: Optional[str] = None
    linked_library_goal_id: Optional[int] = None
    linked_library_strategy_id: Optional[int] = None
    revision_request: Optional[str] = None
    parent_safe: bool = False


class ParentGoalInputCreate(BaseModel):
    goal_ref: str = Field(min_length=1, max_length=64)
    input_type: str
    comment: Optional[str] = Field(default=None, max_length=2000)


class ClinicalAiSessionNoteRequest(BaseModel):
    raw_note: str = Field(min_length=1)
    context: Optional[dict[str, Any]] = None


class ClinicalAiMonthlyDraftRequest(BaseModel):
    section_type: str
    parent_safe: bool = False


class ClinicalAiLanguageCheckRequest(BaseModel):
    text: str = Field(min_length=1)
    context_type: Optional[str] = None
