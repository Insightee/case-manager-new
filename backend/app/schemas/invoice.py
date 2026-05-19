from __future__ import annotations

from typing import Optional

from datetime import datetime

from pydantic import BaseModel

from app.models.invoice import InvoiceStatus


class InvoiceCreate(BaseModel):
    month: str
    amount_inr: float
    sessions_count: int = 0


class InvoiceRead(BaseModel):
    id: int
    therapist_user_id: int
    therapist_name: Optional[str] = None
    month: str
    amount_inr: float
    paid_amount_inr: Optional[float] = None
    sessions_count: int
    status: InvoiceStatus
    reviewer_comment: Optional[str] = None
    created_at: datetime
    subtotal_inr: Optional[float] = None
    leave_deduction_inr: Optional[float] = None
    adjustment_inr: Optional[float] = None
    notes: Optional[str] = None

    model_config = {"from_attributes": True}


class PaymentUpdate(BaseModel):
    paid_amount_inr: float
    status: InvoiceStatus = InvoiceStatus.PAID
