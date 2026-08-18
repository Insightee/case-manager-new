from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class SessionGoalEntry(Base):
    __tablename__ = "session_goal_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    daily_log_id: Mapped[int] = mapped_column(
        ForeignKey("daily_logs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    goal_id: Mapped[int] = mapped_column(ForeignKey("iep_goal_items.id", ondelete="RESTRICT"), nullable=False)
    participation: Mapped[str] = mapped_column(String(32), nullable=False)
    support_level: Mapped[str] = mapped_column(String(32), nullable=False)
    achievement: Mapped[str] = mapped_column(String(32), nullable=False)
    note: Mapped[Optional[str]] = mapped_column(Text)
    created_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class StrategyUseEvent(Base):
    __tablename__ = "strategy_use_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    daily_log_id: Mapped[int] = mapped_column(
        ForeignKey("daily_logs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    strategy_id: Mapped[int] = mapped_column(
        ForeignKey("iep_strategy_items.id", ondelete="RESTRICT"), nullable=False
    )
    response: Mapped[str] = mapped_column(String(32), nullable=False)
    note: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
