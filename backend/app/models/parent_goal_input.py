from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ParentGoalInput(Base):
    __tablename__ = "parent_goal_inputs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), nullable=False, index=True)
    goal_ref: Mapped[str] = mapped_column(String(64), nullable=False)
    input_type: Mapped[str] = mapped_column(String(64), nullable=False)
    comment: Mapped[Optional[str]] = mapped_column(Text)
    parent_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    review_status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
