from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field


class ProductBillingRuleBase(BaseModel):
    product_name: str
    product_category: str
    product_module: str
    billing_model: str
    default_rate_inr: Optional[float] = None
    monthly_fee_inr: Optional[float] = None
    package_sessions: Optional[int] = None
    package_validity_days: Optional[int] = None
    gst_applicable: bool = True
    gst_rate_percent: Optional[float] = None
    hsn_sac_code: Optional[str] = None
    payment_terms: Optional[str] = None
    client_no_show_billable: bool = False
    therapist_cancel_billable: bool = False
    included_paid_leaves: Optional[int] = None
    unpaid_leave_deduction_method: Optional[str] = None
    active: bool = True
    notes: Optional[str] = None


class ProductBillingRuleCreate(ProductBillingRuleBase):
    pass


class ProductBillingRuleUpdate(BaseModel):
    product_name: Optional[str] = None
    product_category: Optional[str] = None
    product_module: Optional[str] = None
    billing_model: Optional[str] = None
    default_rate_inr: Optional[float] = None
    monthly_fee_inr: Optional[float] = None
    package_sessions: Optional[int] = None
    package_validity_days: Optional[int] = None
    gst_applicable: Optional[bool] = None
    gst_rate_percent: Optional[float] = None
    hsn_sac_code: Optional[str] = None
    payment_terms: Optional[str] = None
    client_no_show_billable: Optional[bool] = None
    therapist_cancel_billable: Optional[bool] = None
    included_paid_leaves: Optional[int] = None
    unpaid_leave_deduction_method: Optional[str] = None
    active: Optional[bool] = None
    notes: Optional[str] = None


class ProductBillingRuleRead(ProductBillingRuleBase):
    id: int

    model_config = {"from_attributes": True}


class LedgerOverrideRequest(BaseModel):
    billable_status: str
    override_reason: str = Field(min_length=3)


class GenerateDraftRequest(BaseModel):
    case_id: int
    billing_month: str
    include_pending: bool = False


class OrganisationBase(BaseModel):
    name: str
    gstin: Optional[str] = None
    billing_address: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    active: bool = True


class OrganisationCreate(OrganisationBase):
    pass


class OrganisationRead(OrganisationBase):
    id: int

    model_config = {"from_attributes": True}


class CarePackageAdminCreate(BaseModel):
    case_id: int
    parent_user_id: int
    name: str
    total_sessions: int
    validity_end: Optional[date] = None
    service_label: Optional[str] = None
    product_billing_rule_id: Optional[int] = None
    amount_inr: Optional[float] = None


class CarePackageAdminUpdate(BaseModel):
    name: Optional[str] = None
    total_sessions: Optional[int] = None
    validity_end: Optional[date] = None
    status: Optional[str] = None
    service_label: Optional[str] = None
