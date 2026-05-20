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


class AdminDisputeResolve(BaseModel):
    status: Literal["RESOLVED", "REJECTED"]
    resolution: str = Field(min_length=5)
    adjustment_inr: Optional[float] = None
