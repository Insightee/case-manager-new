from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class RepositoryItemStatus(str, enum.Enum):
    LOCAL = "local"
    CANDIDATE = "candidate"
    APPROVED = "approved"
    ACTIVE = "active"
    ARCHIVED = "archived"


class GoalRepositoryItem(Base):
    __tablename__ = "goal_repository_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[Optional[int]] = mapped_column(ForeignKey("cases.id"), nullable=True, index=True)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    domain_key: Mapped[str] = mapped_column(String(64), nullable=False)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    rationale: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default=RepositoryItemStatus.LOCAL.value, index=True)
    approved_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    source_daily_log_id: Mapped[Optional[int]] = mapped_column(ForeignKey("daily_logs.id"), nullable=True)
    source_session_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    review_note: Mapped[Optional[str]] = mapped_column(Text)
    core_domains_json: Mapped[Optional[str]] = mapped_column(Text)
    core_environments_json: Mapped[Optional[str]] = mapped_column(Text)
    baseline_state: Mapped[Optional[str]] = mapped_column(Text)
    desired_state: Mapped[Optional[str]] = mapped_column(Text)
    goal_statement: Mapped[Optional[str]] = mapped_column(Text)
    lifecycle_status: Mapped[Optional[str]] = mapped_column(String(32))
    source: Mapped[Optional[str]] = mapped_column(String(32))
    scope: Mapped[Optional[str]] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class StrategyRepositoryItem(Base):
    __tablename__ = "strategy_repository_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[Optional[int]] = mapped_column(ForeignKey("cases.id"), nullable=True, index=True)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    when_to_use: Mapped[Optional[str]] = mapped_column(Text)
    how_to_use: Mapped[Optional[str]] = mapped_column(Text)
    avoid: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default=RepositoryItemStatus.LOCAL.value, index=True)
    approved_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    domain_key: Mapped[Optional[str]] = mapped_column(String(64))
    environment_context: Mapped[Optional[str]] = mapped_column(String(32))
    linked_goal_card_id: Mapped[Optional[int]] = mapped_column(ForeignKey("iep_goal_cards.id"), nullable=True)
    source_daily_log_id: Mapped[Optional[int]] = mapped_column(ForeignKey("daily_logs.id"), nullable=True)
    review_note: Mapped[Optional[str]] = mapped_column(Text)
    core_domains_json: Mapped[Optional[str]] = mapped_column(Text)
    core_environments_json: Mapped[Optional[str]] = mapped_column(Text)
    strategy_steps_json: Mapped[Optional[str]] = mapped_column(Text)
    expected_outcome: Mapped[Optional[str]] = mapped_column(Text)
    source: Mapped[Optional[str]] = mapped_column(String(32))
    scope: Mapped[Optional[str]] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class RepositoryReviewEvent(Base):
    __tablename__ = "repository_review_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    item_type: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    item_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    note: Mapped[Optional[str]] = mapped_column(Text)
    merged_into_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
