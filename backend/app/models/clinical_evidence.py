from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class SupportLevel(str, enum.Enum):
    MINIMUM = "MINIMUM"
    MODERATE = "MODERATE"
    MAXIMUM = "MAXIMUM"


class SessionGoalEntry(Base):
    __tablename__ = "session_goal_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    daily_log_id: Mapped[int] = mapped_column(ForeignKey("daily_logs.id", ondelete="CASCADE"), nullable=False, index=True)
    goal_card_id: Mapped[Optional[int]] = mapped_column(ForeignKey("iep_goal_cards.id"), nullable=True, index=True)
    goal_label: Mapped[str] = mapped_column(Text, nullable=False)
    domain_key: Mapped[Optional[str]] = mapped_column(String(64))
    support_level: Mapped[Optional[str]] = mapped_column(String(16))
    response_note: Mapped[Optional[str]] = mapped_column(Text)
    visibility: Mapped[str] = mapped_column(String(32), default="INTERNAL_ONLY")
    session_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    case_id: Mapped[Optional[int]] = mapped_column(ForeignKey("cases.id"), nullable=True, index=True)
    child_id: Mapped[Optional[int]] = mapped_column(ForeignKey("children.id"), nullable=True)
    created_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    participation_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    independence_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    goal_achievement_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    participation: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    independence_support_needed: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    goal_achievement: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    activity_used: Mapped[Optional[str]] = mapped_column(Text)
    measurement_note: Mapped[Optional[str]] = mapped_column(Text)
    core_domains_json: Mapped[Optional[str]] = mapped_column(Text)
    core_environments_json: Mapped[Optional[str]] = mapped_column(Text)
    goal_repository_item_id: Mapped[Optional[int]] = mapped_column(ForeignKey("goal_repository_items.id"), nullable=True)
    evidence_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    clinical_extension_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class StrategyUseEvent(Base):
    __tablename__ = "strategy_use_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    daily_log_id: Mapped[int] = mapped_column(ForeignKey("daily_logs.id", ondelete="CASCADE"), nullable=False, index=True)
    strategy_id: Mapped[Optional[int]] = mapped_column(ForeignKey("strategy_repository_items.id"), nullable=True, index=True)
    strategy_label: Mapped[str] = mapped_column(Text, nullable=False)
    outcome_note: Mapped[Optional[str]] = mapped_column(Text)
    session_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    case_id: Mapped[Optional[int]] = mapped_column(ForeignKey("cases.id"), nullable=True, index=True)
    child_id: Mapped[Optional[int]] = mapped_column(ForeignKey("children.id"), nullable=True)
    goal_card_id: Mapped[Optional[int]] = mapped_column(ForeignKey("iep_goal_cards.id"), nullable=True)
    goal_entry_id: Mapped[Optional[int]] = mapped_column(ForeignKey("session_goal_entries.id"), nullable=True)
    created_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    environment: Mapped[Optional[str]] = mapped_column(String(32))
    activity_used: Mapped[Optional[str]] = mapped_column(Text)
    participation_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    independence_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    goal_achievement_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    participation: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    independence_support_needed: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    goal_achievement: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    strategy_feedback: Mapped[Optional[str]] = mapped_column(String(32))
    short_note: Mapped[Optional[str]] = mapped_column(Text)
    custom_strategy_id: Mapped[Optional[int]] = mapped_column(ForeignKey("strategy_repository_items.id"), nullable=True)
    clinical_extension_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class GoalEvidenceEvent(Base):
    __tablename__ = "goal_evidence_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), nullable=False, index=True)
    domain_key: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_id: Mapped[Optional[int]] = mapped_column(Integer)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    visibility: Mapped[str] = mapped_column(String(32), default="INTERNAL_ONLY")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class IepGoalCard(Base):
    __tablename__ = "iep_goal_cards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    iep_plan_id: Mapped[int] = mapped_column(ForeignKey("iep_plans.id", ondelete="CASCADE"), nullable=False, index=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), nullable=False, index=True)
    domain_key: Mapped[str] = mapped_column(String(64), nullable=False)
    priority_rank: Mapped[Optional[int]] = mapped_column(Integer)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    why_it_matters: Mapped[Optional[str]] = mapped_column(Text)
    baseline: Mapped[Optional[str]] = mapped_column(Text)
    goal_statement: Mapped[Optional[str]] = mapped_column(Text)
    settings_json: Mapped[Optional[str]] = mapped_column(Text)
    success_indicators_json: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="active")
    repository_item_id: Mapped[Optional[int]] = mapped_column(ForeignKey("goal_repository_items.id"))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class IepSupportPriority(Base):
    __tablename__ = "iep_support_priorities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    iep_plan_id: Mapped[int] = mapped_column(ForeignKey("iep_plans.id", ondelete="CASCADE"), nullable=False, index=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), nullable=False, index=True)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[Optional[str]] = mapped_column(String(32))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MonthlyReportSection(Base):
    __tablename__ = "monthly_report_sections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("monthly_reports.id", ondelete="CASCADE"), nullable=False, index=True)
    domain_key: Mapped[Optional[str]] = mapped_column(String(64))
    section_key: Mapped[str] = mapped_column(String(64), nullable=False)
    content_html: Mapped[Optional[str]] = mapped_column(Text)
    visibility: Mapped[str] = mapped_column(String(32), default="INTERNAL_ONLY")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ProgressReportSection(Base):
    __tablename__ = "progress_report_sections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("monthly_reports.id", ondelete="CASCADE"), nullable=False, index=True)
    section_key: Mapped[str] = mapped_column(String(64), nullable=False)
    content_html: Mapped[Optional[str]] = mapped_column(Text)
    visibility: Mapped[str] = mapped_column(String(32), default="INTERNAL_ONLY")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
