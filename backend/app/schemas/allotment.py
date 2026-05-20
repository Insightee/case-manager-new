from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, EmailStr, Field

from app.schemas.case import CaseCreate
from app.schemas.billing import CaseBillingFields
from app.schemas.case import CaseServiceAddressFields


class ChildCreate(BaseModel):
    first_name: str = Field(min_length=1)
    last_name: str = Field(min_length=1)
    date_of_birth: Optional[date] = None


class FamilyCreate(BaseModel):
    parent_email: EmailStr
    parent_full_name: str
    parent_phone: Optional[str] = None
    child: ChildCreate
    send_invite: bool = True
    password: Optional[str] = None


class CaseAllotRequest(CaseBillingFields, CaseServiceAddressFields):
    child_id: int
    service_type: str
    product_module: str
    case_code: Optional[str] = None
    client_billing_mode: Optional[str] = None
    case_manager_user_id: Optional[int] = None
    region: Optional[str] = None
    notes: Optional[str] = None
    therapist_user_id: int
    assignment_start_date: Optional[date] = None
    reason_for_change: Optional[str] = "Initial allotment"


class CaseCreateExtended(CaseCreate):
    case_code: Optional[str] = None
    client_billing_mode: Optional[str] = None
