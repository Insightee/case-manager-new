from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class IepReviewSuggestionStatus(str, enum.Enum):
    DRAFT = "draft"
    ACCEPTED = "accepted"
    DISMISSED = "dismissed"
    CONVERTED_TO_GOAL = "converted_to_goal"
    CONVERTED_TO_STRATEGY = "converted_to_strategy"


class IepReviewSuggestion(Base):
    __tablename__ = "iep_review_suggestions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), nullable=False, index=True)
    iep_plan_id: Mapped[Optional[int]] = mapped_column(ForeignKey("iep_plans.id"), index=True)
    goal_card_id: Mapped[Optional[int]] = mapped_column(ForeignKey("iep_goal_cards.id"))
    strategy_id: Mapped[Optional[int]] = mapped_column(ForeignKey("strategy_repository_items.id"))
    suggestion_type: Mapped[str] = mapped_column(String(64), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    supporting_evidence_json: Mapped[Optional[str]] = mapped_column(Text)
    confidence: Mapped[Optional[str]] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(32), default=IepReviewSuggestionStatus.DRAFT.value, index=True)
    dismissed_reason: Mapped[Optional[str]] = mapped_column(Text)
    created_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
