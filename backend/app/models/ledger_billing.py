from __future__ import annotations

import enum
from datetime import date, datetime
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ProductBillingModel(str, enum.Enum):
    POSTPAID_PER_SESSION = "POSTPAID_PER_SESSION"
    PREPAID_PACKAGE = "PREPAID_PACKAGE"
    MONTHLY_FIXED = "MONTHLY_FIXED"


class LedgerSourceType(str, enum.Enum):
    SESSION = "SESSION"
    DAILY_LOG = "DAILY_LOG"
    LEAVE = "LEAVE"
    MANUAL = "MANUAL"
    MONTHLY_FEE = "MONTHLY_FEE"
    PACKAGE_PURCHASE = "PACKAGE_PURCHASE"
    PACKAGE_CONSUMPTION = "PACKAGE_CONSUMPTION"


class LedgerEventType(str, enum.Enum):
    SESSION_COMPLETED = "SESSION_COMPLETED"
    SESSION_CANCELLED = "SESSION_CANCELLED"
    CLIENT_NO_SHOW = "CLIENT_NO_SHOW"
    THERAPIST_CANCEL = "THERAPIST_CANCEL"
    MONTHLY_FEE = "MONTHLY_FEE"
    LEAVE_DEDUCTION = "LEAVE_DEDUCTION"
    PACKAGE_CONSUMPTION = "PACKAGE_CONSUMPTION"
    MANUAL_ADJUSTMENT = "MANUAL_ADJUSTMENT"


class BillableStatus(str, enum.Enum):
    PENDING_REVIEW = "PENDING_REVIEW"
    BILLABLE = "BILLABLE"
    NON_BILLABLE = "NON_BILLABLE"
    INVOICED = "INVOICED"
    EXCLUDED = "EXCLUDED"


class LedgerDisputeStatus(str, enum.Enum):
    NONE = "NONE"
    OPEN = "OPEN"
    RESOLVED = "RESOLVED"


class ProductBillingRule(Base):
    __tablename__ = "product_billing_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_name: Mapped[str] = mapped_column(String(128), nullable=False)
    product_category: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    product_module: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    billing_model: Mapped[ProductBillingModel] = mapped_column(Enum(ProductBillingModel), nullable=False)
    default_rate_inr: Mapped[Optional[float]] = mapped_column(Numeric(12, 2))
    monthly_fee_inr: Mapped[Optional[float]] = mapped_column(Numeric(12, 2))
    package_sessions: Mapped[Optional[int]] = mapped_column(Integer)
    package_validity_days: Mapped[Optional[int]] = mapped_column(Integer)
    gst_applicable: Mapped[bool] = mapped_column(Boolean, default=True)
    gst_rate_percent: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    hsn_sac_code: Mapped[Optional[str]] = mapped_column(String(16))
    payment_terms: Mapped[Optional[str]] = mapped_column(String(64))
    client_no_show_billable: Mapped[bool] = mapped_column(Boolean, default=False)
    therapist_cancel_billable: Mapped[bool] = mapped_column(Boolean, default=False)
    included_paid_leaves: Mapped[Optional[int]] = mapped_column(Integer)
    unpaid_leave_deduction_method: Mapped[Optional[str]] = mapped_column(String(64))
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class BillingLedger(Base):
    __tablename__ = "billing_ledger"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), nullable=False, index=True)
    parent_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), index=True)
    therapist_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), index=True)
    product_billing_rule_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("product_billing_rules.id"), index=True
    )
    source_type: Mapped[LedgerSourceType] = mapped_column(Enum(LedgerSourceType), nullable=False)
    source_id: Mapped[Optional[int]] = mapped_column(Integer, index=True)
    session_id: Mapped[Optional[int]] = mapped_column(ForeignKey("sessions.id"), index=True)
    daily_log_id: Mapped[Optional[int]] = mapped_column(ForeignKey("daily_logs.id"), index=True)
    ledger_month: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    event_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    event_type: Mapped[LedgerEventType] = mapped_column(Enum(LedgerEventType), nullable=False)
    billable_status: Mapped[BillableStatus] = mapped_column(
        Enum(BillableStatus), default=BillableStatus.PENDING_REVIEW, index=True
    )
    quantity: Mapped[float] = mapped_column(Numeric(8, 2), default=1)
    rate_inr: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    amount_inr: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    gst_rate_percent: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    gst_amount_inr: Mapped[Optional[float]] = mapped_column(Numeric(12, 2))
    hsn_sac_code: Mapped[Optional[str]] = mapped_column(String(16))
    total_inr: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    payout_amount_inr: Mapped[Optional[float]] = mapped_column(Numeric(12, 2))
    insighte_margin_inr: Mapped[Optional[float]] = mapped_column(Numeric(12, 2))
    client_invoice_id: Mapped[Optional[int]] = mapped_column(ForeignKey("client_invoices.id"), index=True)
    care_package_id: Mapped[Optional[int]] = mapped_column(ForeignKey("care_packages.id"), index=True)
    dispute_status: Mapped[LedgerDisputeStatus] = mapped_column(
        Enum(LedgerDisputeStatus), default=LedgerDisputeStatus.NONE
    )
    admin_note: Mapped[Optional[str]] = mapped_column(Text)
    overridden_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    override_reason: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    product_rule = relationship("ProductBillingRule")
    case = relationship("Case", foreign_keys=[case_id])


class Organisation(Base):
    __tablename__ = "organisations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    gstin: Mapped[Optional[str]] = mapped_column(String(32))
    billing_address: Mapped[Optional[str]] = mapped_column(Text)
    contact_email: Mapped[Optional[str]] = mapped_column(String(255))
    contact_phone: Mapped[Optional[str]] = mapped_column(String(32))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
