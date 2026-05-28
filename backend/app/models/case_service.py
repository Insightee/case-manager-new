from __future__ import annotations

from datetime import date, datetime
from typing import Optional

import enum
from sqlalchemy import Date, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class CaseServiceStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    CLOSED = "CLOSED"


class CaseService(Base):
    __tablename__ = "case_services"
    __table_args__ = (
        UniqueConstraint("case_id", "service_key", "status", name="uq_case_services_case_service_status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), nullable=False, index=True)
    service_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    product_module: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    status: Mapped[CaseServiceStatus] = mapped_column(
        Enum(CaseServiceStatus), default=CaseServiceStatus.ACTIVE, nullable=False, index=True
    )
    start_date: Mapped[Optional[date]] = mapped_column(Date)
    end_date: Mapped[Optional[date]] = mapped_column(Date)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    case = relationship("Case", back_populates="services")
    assignments = relationship("CaseAssignment", back_populates="case_service")
