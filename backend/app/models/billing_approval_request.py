from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Integer, Numeric, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class BillingApprovalStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class BillingApprovalRequest(Base):
    __tablename__ = "billing_approval_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), nullable=False, index=True)
    status: Mapped[BillingApprovalStatus] = mapped_column(
        Enum(BillingApprovalStatus),
        nullable=False,
        default=BillingApprovalStatus.PENDING,
        index=True,
    )
    previous_billing: Mapped[dict] = mapped_column(JSON, nullable=False)
    proposed_billing: Mapped[dict] = mapped_column(JSON, nullable=False)
    projected_profit_inr: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    requested_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    reviewed_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    applied_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    case = relationship("Case", lazy="select")
    requester = relationship("User", foreign_keys=[requested_by_user_id], lazy="select")
    reviewer = relationship("User", foreign_keys=[reviewed_by_user_id], lazy="select")
