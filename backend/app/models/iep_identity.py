from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class IepGoalItem(Base):
    """Durable goal identity for a single IEP version. Content SoT remains sections_json."""

    __tablename__ = "iep_goal_items"
    __table_args__ = (
        UniqueConstraint("iep_plan_id", "statement", name="uq_iep_goal_items_plan_statement"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    iep_plan_id: Mapped[int] = mapped_column(ForeignKey("iep_plans.id"), nullable=False, index=True)
    statement: Mapped[str] = mapped_column(String(500), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    retired_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class IepStrategyItem(Base):
    """Durable strategy identity for a single IEP version. Content SoT remains sections_json."""

    __tablename__ = "iep_strategy_items"
    __table_args__ = (
        UniqueConstraint("iep_plan_id", "statement", name="uq_iep_strategy_items_plan_statement"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    iep_plan_id: Mapped[int] = mapped_column(ForeignKey("iep_plans.id"), nullable=False, index=True)
    statement: Mapped[str] = mapped_column(String(500), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    retired_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
