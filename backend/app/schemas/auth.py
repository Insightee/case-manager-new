from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, EmailStr

from app.schemas.address import AddressRead


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class ModuleSummary(BaseModel):
    id: str
    label: str
    description: str
    case_product_modules: list[str] = []
    features: list[str] = []


class UserMeResponse(BaseModel):
    id: int
    email: str
    full_name: str
    avatar_url: Optional[str] = None
    roles: list[str]
    permissions: list[str]
    region: Optional[str] = None
    location: Optional[str] = None
    home_address: Optional[AddressRead] = None
    employment_status: str = "ACTIVE"
    module_assignments: list[str] = []
    features: list[str] = []
    modules: list[ModuleSummary] = []

    model_config = {"from_attributes": True}


class AcceptInviteRequest(BaseModel):
    token: str
    full_name: str
    password: str


class MeUpdate(BaseModel):
    full_name: Optional[str] = None
    location: Optional[str] = None
    employment_status: Optional[str] = None
    home_address_line1: Optional[str] = None
    home_address_line2: Optional[str] = None
    home_city: Optional[str] = None
    home_state: Optional[str] = None
    home_pincode: Optional[str] = None
    home_landmark: Optional[str] = None
    home_latitude: Optional[float] = None
    home_longitude: Optional[float] = None
