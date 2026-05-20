from __future__ import annotations

import enum
from datetime import date, datetime
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ClientInvoiceType(str, enum.Enum):
    PREPAID = "PREPAID"
    POSTPAID = "POSTPAID"


class ClientInvoiceStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    GENERATED = "GENERATED"
    SENT = "SENT"
    PARTIALLY_PAID = "PARTIALLY_PAID"
    PAID = "PAID"
    OVERDUE = "OVERDUE"
    DISPUTED = "DISPUTED"
    CANCELLED = "CANCELLED"


class CarePackageStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"
    EXHAUSTED = "EXHAUSTED"


class PaymentMethod(str, enum.Enum):
    UPI = "UPI"
    BANK_TRANSFER = "BANK_TRANSFER"
    CASH = "CASH"
    CHEQUE = "CHEQUE"
    GATEWAY = "GATEWAY"


class BillingDisputeStatus(str, enum.Enum):
    OPEN = "OPEN"
    UNDER_REVIEW = "UNDER_REVIEW"
    RESOLVED = "RESOLVED"
    REJECTED = "REJECTED"


class ClientInvoice(Base):
    """Family-facing invoice (separate from therapist payout invoices)."""

    __tablename__ = "client_invoices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    invoice_number: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    parent_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), nullable=False, index=True)
    invoice_type: Mapped[ClientInvoiceType] = mapped_column(Enum(ClientInvoiceType), nullable=False)
    status: Mapped[ClientInvoiceStatus] = mapped_column(
        Enum(ClientInvoiceStatus), default=ClientInvoiceStatus.GENERATED
    )
    billing_month: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    service_type: Mapped[str] = mapped_column(String(128), nullable=False)
    product_module: Mapped[str] = mapped_column(String(64), nullable=False)
    due_date: Mapped[Optional[date]] = mapped_column(Date)
    subtotal_inr: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    tax_inr: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    discount_inr: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    package_deduction_inr: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    adjustment_inr: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    total_inr: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    amount_paid_inr: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    lines = relationship("ClientInvoiceLine", back_populates="invoice", cascade="all, delete-orphan")
    payments = relationship("ClientPayment", back_populates="invoice", cascade="all, delete-orphan")
    disputes = relationship("BillingDispute", back_populates="invoice", cascade="all, delete-orphan")


class ClientInvoiceLine(Base):
    __tablename__ = "client_invoice_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    client_invoice_id: Mapped[int] = mapped_column(ForeignKey("client_invoices.id"), nullable=False, index=True)
    session_id: Mapped[Optional[int]] = mapped_column(ForeignKey("sessions.id"))
    daily_log_id: Mapped[Optional[int]] = mapped_column(ForeignKey("daily_logs.id"))
    session_date: Mapped[date] = mapped_column(Date, nullable=False)
    therapist_name: Mapped[str] = mapped_column(String(128), nullable=False)
    service_label: Mapped[str] = mapped_column(String(128), nullable=False)
    session_status: Mapped[str] = mapped_column(String(64), nullable=False)
    amount_inr: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    package_deducted: Mapped[bool] = mapped_column(Boolean, default=False)
    parent_summary: Mapped[Optional[str]] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    invoice = relationship("ClientInvoice", back_populates="lines")


class CarePackage(Base):
    __tablename__ = "care_packages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), nullable=False, index=True)
    parent_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    total_sessions: Mapped[int] = mapped_column(Integer, nullable=False)
    used_sessions: Mapped[int] = mapped_column(Integer, default=0)
    validity_end: Mapped[Optional[date]] = mapped_column(Date)
    service_label: Mapped[Optional[str]] = mapped_column(String(128))
    status: Mapped[CarePackageStatus] = mapped_column(Enum(CarePackageStatus), default=CarePackageStatus.ACTIVE)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ClientPayment(Base):
    __tablename__ = "client_payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    client_invoice_id: Mapped[int] = mapped_column(ForeignKey("client_invoices.id"), nullable=False, index=True)
    amount_inr: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    method: Mapped[PaymentMethod] = mapped_column(Enum(PaymentMethod), nullable=False)
    reference: Mapped[Optional[str]] = mapped_column(String(128))
    paid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    recorded_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    notes: Mapped[Optional[str]] = mapped_column(Text)

    invoice = relationship("ClientInvoice", back_populates="payments")


class BillingDispute(Base):
    __tablename__ = "billing_disputes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    client_invoice_id: Mapped[int] = mapped_column(ForeignKey("client_invoices.id"), nullable=False, index=True)
    client_invoice_line_id: Mapped[Optional[int]] = mapped_column(ForeignKey("client_invoice_lines.id"))
    parent_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    reason_code: Mapped[str] = mapped_column(String(64), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[BillingDisputeStatus] = mapped_column(
        Enum(BillingDisputeStatus), default=BillingDisputeStatus.OPEN
    )
    admin_resolution: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    invoice = relationship("ClientInvoice", back_populates="disputes")
