from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class TherapistPayoutBatchStatus(str, enum.Enum):
    PENDING = "PENDING"
    EXPORTED = "EXPORTED"
    PROCESSING = "PROCESSING"
    PAID = "PAID"
    PARTIAL_FAILED = "PARTIAL_FAILED"
    FAILED = "FAILED"


class TherapistPayoutTransferStatus(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    PAID = "PAID"
    FAILED = "FAILED"


class TherapistPayoutBatch(Base):
    __tablename__ = "therapist_payout_batches"
    __table_args__ = (UniqueConstraint("idempotency_key", name="uq_therapist_payout_batches_idempotency"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    billing_month: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=TherapistPayoutBatchStatus.PENDING.value)
    provider: Mapped[str] = mapped_column(String(32), nullable=False, default="MOCK")
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    provider_batch_ref: Mapped[Optional[str]] = mapped_column(String(128))
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    transfers = relationship("TherapistPayoutTransfer", back_populates="batch", cascade="all, delete-orphan")


class TherapistPayoutTransfer(Base):
    __tablename__ = "therapist_payout_transfers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("therapist_payout_batches.id"), nullable=False, index=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id"), nullable=False, index=True)
    gross_inr: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    tds_rate_percent: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False)
    tds_inr: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    deductions_inr: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    net_inr: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    provider_ref: Mapped[Optional[str]] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=TherapistPayoutTransferStatus.PENDING.value)
    failure_reason: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    batch = relationship("TherapistPayoutBatch", back_populates="transfers")
