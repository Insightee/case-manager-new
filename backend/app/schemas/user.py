from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.core.departments import validate_staff_department


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

    @field_validator("department")
    @classmethod
    def _validate_department(cls, value: Optional[str]) -> Optional[str]:
        return validate_staff_department(value)


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

    @field_validator("department")
    @classmethod
    def _validate_department(cls, value: Optional[str]) -> Optional[str]:
        return validate_staff_department(value)


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
