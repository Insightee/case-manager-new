from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class TherapistProfileBase(BaseModel):
    display_name: Optional[str] = Field(None, max_length=255)
    short_bio: Optional[str] = Field(None, max_length=2000)
    academic_qualifications: Optional[str] = Field(None, max_length=4000)
    professional_certificates: list[str] = Field(default_factory=list)
    services_offered: list[str] = Field(default_factory=list)


class TherapistProfileUpdate(TherapistProfileBase):
    supervisor_user_id: Optional[int] = None
    mentor_user_id: Optional[int] = None


class TherapistProfileRead(TherapistProfileBase):
    id: int
    user_id: int
    status: str
    admin_note: Optional[str] = None
    submitted_at: Optional[datetime] = None
    reviewed_at: Optional[datetime] = None
    email: Optional[str] = None
    full_name: Optional[str] = None
    supervisor_user_id: Optional[int] = None
    mentor_user_id: Optional[int] = None
    supervisor_name: Optional[str] = None
    mentor_name: Optional[str] = None

    model_config = {"from_attributes": True}


class TherapistProfileAdminCreate(TherapistProfileBase):
    user_id: int
    status: Optional[str] = "APPROVED"
    supervisor_user_id: Optional[int] = None
    mentor_user_id: Optional[int] = None


class TherapistProfileReview(BaseModel):
    admin_note: Optional[str] = None


class ServiceCategoryRead(BaseModel):
    id: str
    label: str
    description: Optional[str] = None
    sort_order: int = 0
    is_active: bool = True


class ServiceCategoryCreate(BaseModel):
    id: Optional[str] = None
    label: str = Field(min_length=2, max_length=255)
    description: Optional[str] = None
    sort_order: int = 0
