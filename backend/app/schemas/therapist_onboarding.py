from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, EmailStr, Field


class TherapistOnboardCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=255)
    external_employee_id: Optional[str] = Field(None, max_length=64)
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
    external_employee_id: Optional[str] = Field(None, max_length=64)
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


class TherapistPrimaryCmBulkRow(BaseModel):
    therapist_id: Optional[str] = Field(None, max_length=64)
    email: Optional[str] = None
    primary_cm_name: Optional[str] = Field(None, max_length=255)
    case_manager_email: str = Field(min_length=3, max_length=255)


class TherapistPrimaryCmBulkRequest(BaseModel):
    rows: list[TherapistPrimaryCmBulkRow] = Field(min_length=1, max_length=500)
    apply: bool = False


class TherapistPrimaryCmBulkRowResult(BaseModel):
    row_index: int
    therapist_email: Optional[str] = None
    therapist_id: Optional[str] = None
    case_manager_email: str
    primary_cm_name: Optional[str] = None
    status: str
    message: Optional[str] = None
    warning: Optional[str] = None
    profile_updated: bool = False
    cases_updated: int = 0
    old_cm_email: Optional[str] = None
    new_cm_email: Optional[str] = None


class TherapistPrimaryCmBulkResponse(BaseModel):
    apply: bool
    summary: dict
    results: list[TherapistPrimaryCmBulkRowResult]
