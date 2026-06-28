from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class MonthlyReportEvidenceSnapshot(Base):
    __tablename__ = "monthly_report_evidence_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    report_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    clinical_report_id: Mapped[Optional[int]] = mapped_column(ForeignKey("clinical_reports.id"), nullable=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), nullable=False, index=True)
    month: Mapped[str] = mapped_column(String(7), nullable=False)
    evidence_json: Mapped[str] = mapped_column(Text, nullable=False)
    source_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    compiler_version: Mapped[str] = mapped_column(String(16), default="1.0.0", nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    generated_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
