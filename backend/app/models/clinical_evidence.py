from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


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
