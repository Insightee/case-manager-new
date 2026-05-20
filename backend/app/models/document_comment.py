from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class DocumentEntityType(str, enum.Enum):
    IEP = "iep"
    MONTHLY_REPORT = "monthly_report"


class CommentType(str, enum.Enum):
    GENERAL = "GENERAL"
    GOAL_SUGGESTION = "GOAL_SUGGESTION"
    CHANGE_REQUEST = "CHANGE_REQUEST"


class DocumentComment(Base):
    __tablename__ = "document_comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True)
    author_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    comment_type: Mapped[str] = mapped_column(String(32), nullable=False, default=CommentType.GENERAL.value)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
