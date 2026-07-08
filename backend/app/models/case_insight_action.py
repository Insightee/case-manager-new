from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class InsightActionDestination(str, enum.Enum):
    MONTHLY_REPORT = "monthly_report"
    IEP_REVIEW = "iep_review"


class InsightActionStatus(str, enum.Enum):
    PENDING_REVIEW = "pending_review"
    INCORPORATED = "incorporated"
    DISMISSED = "dismissed"


class CaseInsightAction(Base):
    """Staged selection of a rule-based insight card for a monthly report or IEP review.

    Selecting an insight never writes report text directly — it lands here in
    `pending_review` so a Case Manager sees it in the exception queue, matching the
    "remain editable and require therapist review" doctrine constraint.
    """

    __tablename__ = "case_insight_actions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), nullable=False, index=True)
    insight_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    insight_snapshot_json: Mapped[str] = mapped_column(Text, nullable=False)
    destination: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=InsightActionStatus.PENDING_REVIEW.value, index=True)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), onupdate=func.now())
