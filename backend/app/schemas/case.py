from __future__ import annotations

from typing import Optional

from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models.case import CaseStatus
from app.schemas.address import AddressRead
from app.schemas.billing import CaseBillingFields


class CaseServiceAddressFields(BaseModel):
    service_address_line1: Optional[str] = None
    service_address_line2: Optional[str] = None
    service_city: Optional[str] = None
    service_state: Optional[str] = None
    service_pincode: Optional[str] = None
    service_landmark: Optional[str] = None
    service_latitude: Optional[float] = None
    service_longitude: Optional[float] = None


class CaseCreate(CaseBillingFields, CaseServiceAddressFields):
    case_code: Optional[str] = None
    child_id: int
    client_billing_mode: Optional[str] = None
    service_type: str
    product_module: str
    case_manager_user_id: Optional[int] = None
    region: Optional[str] = None
    operational_stage: Optional[str] = None
    notes: Optional[str] = None


class CaseUpdate(CaseBillingFields, CaseServiceAddressFields):
    client_billing_mode: Optional[str] = None
    service_type: Optional[str] = None
    product_module: Optional[str] = None
    status: Optional[CaseStatus] = None
    case_manager_user_id: Optional[int] = None
    region: Optional[str] = None
    operational_stage: Optional[str] = None
    notes: Optional[str] = None


class CaseRead(CaseBillingFields):
    id: int
    case_code: str
    external_case_ref: Optional[str] = None
    child_id: int
    child_name: Optional[str] = None
    service_type: str
    product_module: str
    status: CaseStatus
    case_manager_user_id: Optional[int]
    case_manager_name: Optional[str] = None
    case_manager_email: Optional[str] = None
    notes: Optional[str] = None
    region: Optional[str]
    operational_stage: Optional[str]
    created_at: datetime
    billing_updated_at: Optional[datetime] = None
    service_address: Optional[AddressRead] = None
    maps_url: Optional[str] = None

    model_config = {"from_attributes": True}


class AssignmentCreate(BaseModel):
    therapist_user_id: int
    start_date: date
    reason_for_change: Optional[str] = None
    notes: Optional[str] = None


class AssignmentBookingUpdate(BaseModel):
    booking_mode: Optional[str] = None
    fixed_weekdays: Optional[list[str]] = None
    fixed_start_time: Optional[str] = None
    fixed_end_time: Optional[str] = None
    fixed_recurrence_group_id: Optional[str] = None


class AssignmentRead(BaseModel):
    id: int
    case_id: int
    therapist_user_id: int
    therapist_name: Optional[str] = None
    assigned_by_user_id: Optional[int]
    start_date: date
    end_date: Optional[date]
    status: str
    reason_for_change: Optional[str]
    notes: Optional[str]
    booking_mode: str = "OPEN"
    fixed_weekdays: Optional[list[str]] = None
    fixed_start_time: Optional[str] = None
    fixed_end_time: Optional[str] = None
    fixed_recurrence_group_id: Optional[str] = None
    fixed_window_label: Optional[str] = None
    case_billing: Optional[dict] = None

    model_config = {"from_attributes": True}
