from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from app.core.departments import validate_staff_department
from app.models.user import StaffEmploymentType


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    full_name: str
    role_names: list[str]
    external_employee_id: Optional[str] = Field(None, max_length=64)
    department: Optional[str] = None
    region: Optional[str] = None
    module_assignments: list[str] = []
    module_access_grants: Optional[dict] = None
    service_access_grants: Optional[dict] = None
    org_capability_grants: Optional[dict] = None
    feature_overrides: Optional[dict] = None
    view_only: bool = False
    staff_employment_type: Optional[StaffEmploymentType] = None
    staff_probation_months: Optional[int] = Field(None, ge=1, le=24)
    staff_employment_start_date: Optional[date] = None
    staff_leave_credit_balance: Optional[int] = Field(None, ge=0)

    @field_validator("department")
    @classmethod
    def _validate_department(cls, value: Optional[str]) -> Optional[str]:
        return validate_staff_department(value)

    @model_validator(mode="after")
    def _validate_staff_employment(self) -> "UserCreate":
        if self.staff_employment_type == StaffEmploymentType.PROBATION:
            if not self.staff_probation_months:
                raise ValueError("Probation period (months) is required for Probation employment type.")
            if not self.staff_employment_start_date:
                raise ValueError("Employment start date is required for Probation employment type.")
        elif self.staff_probation_months is not None:
            raise ValueError("Probation period applies only when employment type is Probation.")
        return self


class UserRead(BaseModel):
    id: int
    external_employee_id: Optional[str] = None
    email: str
    full_name: str
    phone: Optional[str] = None
    is_active: bool
    is_view_only: bool = False
    roles: list[str]
    department: Optional[str] = None
    region: Optional[str]
    module_assignments: list[str]
    module_access_grants: dict = Field(default_factory=dict)
    service_access_grants: dict = Field(default_factory=dict)
    org_capability_grants: dict = Field(default_factory=dict)
    feature_overrides: dict = Field(default_factory=dict)
    login_ready: bool = False
    invite_status: Optional[str] = None
    last_invite_sent_at: Optional[str] = None
    pending_invite_url: Optional[str] = None
    email_delivery_status: Optional[str] = None
    email_attempt_count: Optional[int] = None
    last_email_status: Optional[str] = None
    last_email_sent_at: Optional[str] = None
    next_retry_at: Optional[str] = None
    resend_allowed_at: Optional[str] = None
    is_email_suppressed: bool = False
    suppression_reason: Optional[str] = None
    delivery_message: Optional[str] = None
    staff_employment_type: Optional[str] = None
    staff_probation_months: Optional[int] = None
    staff_employment_start_date: Optional[date] = None
    staff_leave_credit_balance: Optional[int] = None

    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    external_employee_id: Optional[str] = Field(None, max_length=64)
    module_assignments: Optional[list[str]] = None
    module_access_grants: Optional[dict] = None
    service_access_grants: Optional[dict] = None
    org_capability_grants: Optional[dict] = None
    feature_overrides: Optional[dict] = None
    role_names: Optional[list[str]] = None
    department: Optional[str] = None
    region: Optional[str] = None
    is_active: Optional[bool] = None
    view_only: Optional[bool] = None
    staff_employment_type: Optional[StaffEmploymentType] = None
    staff_probation_months: Optional[int] = Field(None, ge=1, le=24)
    staff_employment_start_date: Optional[date] = None
    staff_leave_credit_balance: Optional[int] = Field(None, ge=0)

    @field_validator("department")
    @classmethod
    def _validate_department(cls, value: Optional[str]) -> Optional[str]:
        return validate_staff_department(value)

    @model_validator(mode="after")
    def _validate_staff_employment(self) -> "UserUpdate":
        fields = self.model_dump(exclude_unset=True)
        if fields.get("staff_employment_type") == StaffEmploymentType.PROBATION:
            if "staff_probation_months" in fields and fields["staff_probation_months"] is None:
                raise ValueError("Probation period (months) is required for Probation employment type.")
            if "staff_employment_start_date" in fields and fields["staff_employment_start_date"] is None:
                raise ValueError("Employment start date is required for Probation employment type.")
        elif "staff_probation_months" in fields and fields["staff_probation_months"] is not None:
            if fields.get("staff_employment_type") not in (StaffEmploymentType.PROBATION, None):
                raise ValueError("Probation period applies only when employment type is Probation.")
        return self


class UserDirectoryItem(BaseModel):
    id: int
    external_employee_id: Optional[str] = None
    email: str
    full_name: str
    roles: list[str] = Field(default_factory=list)
    department: Optional[str] = None
    phone: Optional[str] = None
    is_active: bool = True
    module_assignments: list[str] = Field(default_factory=list)
    login_ready: bool = False
    invite_status: Optional[str] = None
    pending_invite_url: Optional[str] = None
    last_invite_sent_at: Optional[str] = None
    email_delivery_status: Optional[str] = None
    email_attempt_count: Optional[int] = None
    last_email_status: Optional[str] = None
    last_email_sent_at: Optional[str] = None
    next_retry_at: Optional[str] = None
    resend_allowed_at: Optional[str] = None
    is_email_suppressed: bool = False
    suppression_reason: Optional[str] = None
    delivery_message: Optional[str] = None
    staff_employment_type: Optional[str] = None
    staff_probation_months: Optional[int] = None
    staff_employment_start_date: Optional[date] = None
    staff_leave_credit_balance: Optional[int] = None


class InviteCreate(BaseModel):
    email: EmailStr
    role_name: str
    full_name: Optional[str] = None
    department: Optional[str] = None
    send_email: bool = True
    module_assignments: list[str] = []
    module_access_grants: Optional[dict] = None
    service_access_grants: Optional[dict] = None
    org_capability_grants: Optional[dict] = None
    feature_overrides: Optional[dict] = None
    view_only: bool = False

    @field_validator("department")
    @classmethod
    def _validate_department(cls, value: Optional[str]) -> Optional[str]:
        return validate_staff_department(value)


class AdminSetPassword(BaseModel):
    password: str = Field(min_length=6)
