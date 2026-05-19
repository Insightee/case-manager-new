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
    pass


class TherapistProfileRead(TherapistProfileBase):
    id: int
    user_id: int
    status: str
    admin_note: Optional[str] = None
    submitted_at: Optional[datetime] = None
    reviewed_at: Optional[datetime] = None
    email: Optional[str] = None
    full_name: Optional[str] = None

    model_config = {"from_attributes": True}


class TherapistProfileAdminCreate(TherapistProfileBase):
    user_id: int
    status: Optional[str] = "APPROVED"


class TherapistProfileReview(BaseModel):
    admin_note: Optional[str] = None


class ServiceCategoryRead(BaseModel):
    id: str
    label: str
