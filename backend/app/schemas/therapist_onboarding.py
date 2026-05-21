from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, EmailStr, Field


class TherapistOnboardCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=255)
    phone: Optional[str] = Field(None, max_length=32)
    module_assignments: list[str] = Field(default_factory=lambda: ["homecare", "shadow_support"])
    services_offered: list[str] = Field(default_factory=list)
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


class TherapistOnboardResult(BaseModel):
    email: str
    user_id: Optional[int] = None
    invite_url: Optional[str] = None
    temporary_password: Optional[str] = None
    success: bool
    error: Optional[str] = None
