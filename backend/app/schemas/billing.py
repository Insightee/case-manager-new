from __future__ import annotations

from datetime import date, time
from typing import Optional

from pydantic import BaseModel, Field


class CaseBillingFields(BaseModel):
    billing_type: Optional[str] = None
    client_rate_per_session_inr: Optional[float] = None
    package_session_count: Optional[int] = None
    package_amount_inr: Optional[float] = None
    compensation_mode: Optional[str] = None
    pay_share_pct: Optional[float] = Field(None, ge=50, le=70)
    therapist_fixed_pay_inr: Optional[float] = None
    billing_notes: Optional[str] = None


class LateSessionCreate(BaseModel):
    case_id: int
    session_date: date
    month: str = Field(..., description="Invoice month YYYY-MM or Mon YYYY")
    start_time: time
    end_time: time
    attendance_status: str = "present"
    activities_done: Optional[str] = None
    observations: Optional[str] = None
    late_reason: str = Field(..., min_length=5)


class InvoicePreviewEdit(BaseModel):
    exclude_session_ids: list[int] = []


class InvoiceSubmitRequest(BaseModel):
    month: str
    edits: Optional[InvoicePreviewEdit] = None
    notes: Optional[str] = None
