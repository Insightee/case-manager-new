from __future__ import annotations

from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class BillingDisputeCreate(BaseModel):
    reason_code: Literal[
        "not_attended",
        "therapist_late",
        "duplicate_billing",
        "incorrect_amount",
        "wrong_package_deduction",
        "other",
    ]
    message: str = Field(min_length=10)
    line_id: Optional[int] = None


class ClientPaymentRecord(BaseModel):
    amount_inr: float = Field(gt=0)
    method: Literal["UPI", "BANK_TRANSFER", "CASH", "CHEQUE", "GATEWAY"]
    reference: Optional[str] = None
    notes: Optional[str] = None


class PaymentClaimReject(BaseModel):
    note: str = Field(min_length=3)


class AdminDisputeResolve(BaseModel):
    status: Literal["RESOLVED", "REJECTED"]
    resolution: str = Field(min_length=5)
    adjustment_inr: Optional[float] = None


class ClientInvoiceLineCreate(BaseModel):
    session_date: date
    therapist_name: str = Field(min_length=1, max_length=128)
    service_label: str = Field(min_length=1, max_length=128)
    session_status: str = Field(default="COMPLETED", max_length=64)
    amount_inr: float = Field(gt=0)
    session_id: Optional[int] = None
    daily_log_id: Optional[int] = None
    parent_summary: Optional[str] = None


class AdminClientInvoiceCreate(BaseModel):
    case_id: int
    invoice_type: Literal["PREPAID", "POSTPAID"]
    billing_month: str = Field(min_length=3, max_length=32)
    due_date: Optional[date] = None
    notes: Optional[str] = None
    discount_inr: float = Field(default=0, ge=0)
    lines: list[ClientInvoiceLineCreate] = Field(min_length=1)


class AdminClientInvoiceUpdate(BaseModel):
    due_date: Optional[date] = None
    notes: Optional[str] = None
    discount_inr: Optional[float] = Field(default=None, ge=0)
    adjustment_inr: Optional[float] = None
    status: Optional[Literal["DRAFT", "GENERATED"]] = None
