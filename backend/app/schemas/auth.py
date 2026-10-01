from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.schemas.address import AddressRead


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    portal: Optional[Literal["parent", "therapist", "staff", "admin"]] = None
    remember_me: bool = False

    @field_validator("portal", mode="before")
    @classmethod
    def _normalize_portal(cls, value: object) -> object:
        if value is None or (isinstance(value, str) and not value.strip()):
            return None
        if isinstance(value, str):
            key = value.strip().lower()
            return "staff" if key == "admin" else key
        return value


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: Optional["UserMeResponse"] = None


class RefreshRequest(BaseModel):
    refresh_token: str


class ModuleSummary(BaseModel):
    id: str
    label: str
    description: str
    case_product_modules: list[str] = []
    access: str = "write"
    features: list[str] = []


class ClinicalProductModuleRead(BaseModel):
    id: str
    label: str


class TherapistProfileCompletionRead(BaseModel):
    percent: int = 0
    complete: bool = False
    missing_fields: list[str] = Field(default_factory=list)
    total_steps: int = 0
    completed_steps: int = 0


class UserMeResponse(BaseModel):
    id: int
    email: str
    full_name: str
    staff_id: Optional[str] = None
    phone: Optional[str] = None
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    job_title: Optional[str] = None
    department: Optional[str] = None
    timezone: Optional[str] = None
    ui_preferences: dict = {}
    notification_preferences: dict = {}
    roles: list[str]
    permissions: list[str]
    region: Optional[str] = None
    location: Optional[str] = None
    home_address: Optional[AddressRead] = None
    employment_status: str = "ACTIVE"
    module_assignments: list[str] = []
    is_view_only: bool = False
    features: list[str] = []
    modules: list[ModuleSummary] = []
    profile_completion: Optional[TherapistProfileCompletionRead] = None

    model_config = {"from_attributes": True}


class AcceptInviteRequest(BaseModel):
    token: str
    full_name: str
    password: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ForgotPasswordResponse(BaseModel):
    message: str = (
        "If an account exists for that email, you will receive password reset instructions shortly."
    )


class ResetPasswordPreviewResponse(BaseModel):
    email: str
    login_portal: Optional[Literal["parent", "therapist", "staff"]] = None


TokenResponse.model_rebuild()


class ResetPasswordRequest(BaseModel):
    token: str
    password: str


class MeUpdate(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
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
    bio: Optional[str] = None
    job_title: Optional[str] = None
    timezone: Optional[str] = None
    ui_preferences: Optional[dict] = None
    notification_preferences: Optional[dict] = None
