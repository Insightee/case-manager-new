from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    full_name: str
    role_names: list[str]
    region: Optional[str] = None
    module_assignments: list[str] = []
    module_access_grants: Optional[dict] = None
    service_access_grants: Optional[dict] = None
    org_capability_grants: Optional[dict] = None
    feature_overrides: Optional[dict] = None
    view_only: bool = False


class UserRead(BaseModel):
    id: int
    external_employee_id: Optional[str] = None
    email: str
    full_name: str
    phone: Optional[str] = None
    is_active: bool
    is_view_only: bool = False
    roles: list[str]
    region: Optional[str]
    module_assignments: list[str]
    module_access_grants: dict = Field(default_factory=dict)
    service_access_grants: dict = Field(default_factory=dict)
    org_capability_grants: dict = Field(default_factory=dict)
    feature_overrides: dict = Field(default_factory=dict)

    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    module_assignments: Optional[list[str]] = None
    module_access_grants: Optional[dict] = None
    service_access_grants: Optional[dict] = None
    org_capability_grants: Optional[dict] = None
    feature_overrides: Optional[dict] = None
    role_names: Optional[list[str]] = None
    region: Optional[str] = None
    is_active: Optional[bool] = None
    view_only: Optional[bool] = None


class UserDirectoryItem(BaseModel):
    id: int
    email: str
    full_name: str
    roles: list[str] = Field(default_factory=list)


class InviteCreate(BaseModel):
    email: EmailStr
    role_name: str
    full_name: Optional[str] = None
    send_email: bool = True
    module_assignments: list[str] = []
    module_access_grants: Optional[dict] = None
    service_access_grants: Optional[dict] = None
    org_capability_grants: Optional[dict] = None
    feature_overrides: Optional[dict] = None
    view_only: bool = False


class AdminSetPassword(BaseModel):
    password: str = Field(min_length=6)
