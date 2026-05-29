from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, EmailStr, Field


class TherapistOnboardCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=255)
    phone: Optional[str] = Field(None, max_length=32)
    module_assignments: list[str] = Field(default_factory=list)
    services_offered: list[str] = Field(default_factory=list)
    primary_case_manager_user_id: int = Field(..., description="Primary case manager (supervisor)")
    mentor_user_id: Optional[int] = None
    service_access_grants: Optional[dict] = None
    mode: Literal["invite", "direct"] = "invite"
    password: Optional[str] = Field(None, min_length=6)
    send_email: bool = True
    short_bio: Optional[str] = None


class TherapistBulkRow(BaseModel):
    full_name: str = Field(min_length=1)
    email: EmailStr
    phone: Optional[str] = None
    services_offered: list[str] = Field(default_factory=list)
    module_assignments: list[str] = Field(default_factory=lambda: ["homecare", "shadow_support"])


class TherapistBulkOnboardRequest(BaseModel):
    therapists: list[TherapistBulkRow] = Field(min_length=1, max_length=100)
    mode: Literal["invite", "direct"] = "invite"
    send_email: bool = True
    primary_case_manager_user_id: int = Field(..., description="Primary case manager for all rows")
    mentor_user_id: Optional[int] = None


class TherapistOnboardResult(BaseModel):
    email: str
    user_id: Optional[int] = None
    invite_url: Optional[str] = None
    invite_id: Optional[int] = None
    expires_at: Optional[str] = None
    temporary_password: Optional[str] = None
    email_delivery: Optional[str] = None
    success: bool
    error: Optional[str] = None
