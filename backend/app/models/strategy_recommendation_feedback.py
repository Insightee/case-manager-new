from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class RecommendationSource(str, enum.Enum):
    LIBRARY_MATCH = "library_match"
    BRAIN_RULE = "brain_rule"
    THERAPIST_SEARCH = "therapist_search"
    FUTURE_AI = "future_ai"


class FeedbackStatus(str, enum.Enum):
    ACCEPTED = "accepted"
    ADAPTED = "adapted"
    DISMISSED = "dismissed"
    NOT_RELEVANT = "not_relevant"
    ALREADY_TRIED = "already_tried"
    NEEDS_CM_INPUT = "needs_cm_input"


class StrategyRecommendationFeedback(Base):
    __tablename__ = "strategy_recommendation_feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), nullable=False, index=True)
    child_id: Mapped[Optional[int]] = mapped_column(ForeignKey("children.id"), nullable=True)
    goal_repository_item_id: Mapped[Optional[int]] = mapped_column(ForeignKey("goal_repository_items.id"), nullable=True)
    goal_card_id: Mapped[Optional[int]] = mapped_column(ForeignKey("iep_goal_cards.id"), nullable=True)
    strategy_repository_item_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("strategy_repository_items.id"), nullable=True, index=True
    )
    recommendation_source: Mapped[str] = mapped_column(String(32), default=RecommendationSource.LIBRARY_MATCH.value)
    feedback_status: Mapped[str] = mapped_column(String(32), nullable=False)
    adaptation_text: Mapped[Optional[str]] = mapped_column(Text)
    dismissal_reason: Mapped[Optional[str]] = mapped_column(Text)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_by_role: Mapped[Optional[str]] = mapped_column(String(32))
    source_context_json: Mapped[Optional[str]] = mapped_column(Text)
    parent_visible: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    review_status: Mapped[Optional[str]] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
