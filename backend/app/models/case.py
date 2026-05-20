from __future__ import annotations

from typing import Optional

import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class CaseStatus(str, enum.Enum):
    PENDING_ALLOTMENT = "PENDING_ALLOTMENT"
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    CLOSED = "CLOSED"


class BillingType(str, enum.Enum):
    PER_SESSION = "PER_SESSION"
    PACKAGE = "PACKAGE"


class CompensationMode(str, enum.Enum):
    PERCENTAGE = "PERCENTAGE"
    FIXED_LUMP = "FIXED_LUMP"


class ClientBillingMode(str, enum.Enum):
    PREPAID = "PREPAID"
    POSTPAID = "POSTPAID"


class Case(Base):
    __tablename__ = "cases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    child_id: Mapped[int] = mapped_column(ForeignKey("children.id"), nullable=False, index=True)
    service_type: Mapped[str] = mapped_column(String(128), nullable=False)
    product_module: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[CaseStatus] = mapped_column(Enum(CaseStatus), default=CaseStatus.PENDING_ALLOTMENT, index=True)
    case_manager_user_id: Mapped[Optional[int ]] = mapped_column(ForeignKey("users.id"), index=True)
    region: Mapped[Optional[str ]] = mapped_column(String(64))
    operational_stage: Mapped[Optional[str ]] = mapped_column(String(64))
    notes: Mapped[Optional[str]] = mapped_column(Text)
    billing_type: Mapped[Optional[BillingType]] = mapped_column(Enum(BillingType))
    client_rate_per_session_inr: Mapped[Optional[float]] = mapped_column(Numeric(12, 2))
    package_session_count: Mapped[Optional[int]] = mapped_column(Integer)
    package_amount_inr: Mapped[Optional[float]] = mapped_column(Numeric(12, 2))
    compensation_mode: Mapped[Optional[CompensationMode]] = mapped_column(Enum(CompensationMode))
    pay_share_pct: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    therapist_fixed_pay_inr: Mapped[Optional[float]] = mapped_column(Numeric(12, 2))
    billing_notes: Mapped[Optional[str]] = mapped_column(Text)
    client_billing_mode: Mapped[Optional[ClientBillingMode]] = mapped_column(Enum(ClientBillingMode))
    billing_updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    billing_updated_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    service_address_line1: Mapped[Optional[str]] = mapped_column(String(255))
    service_address_line2: Mapped[Optional[str]] = mapped_column(String(255))
    service_city: Mapped[Optional[str]] = mapped_column(String(128))
    service_state: Mapped[Optional[str]] = mapped_column(String(128))
    service_pincode: Mapped[Optional[str]] = mapped_column(String(16))
    service_landmark: Mapped[Optional[str]] = mapped_column(String(255))
    service_latitude: Mapped[Optional[float]] = mapped_column(Float)
    service_longitude: Mapped[Optional[float]] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    child = relationship("Child", back_populates="cases")
    assignments = relationship("CaseAssignment", back_populates="case")
    sessions = relationship("Session", back_populates="case")
