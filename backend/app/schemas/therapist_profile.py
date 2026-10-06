from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class QualificationEntry(BaseModel):
    kind: Literal["degree", "certificate"] = "certificate"
    title: str = Field(..., min_length=1, max_length=255)
    year: Optional[int] = Field(None, ge=1950, le=2035)


class QualificationEntryRead(BaseModel):
    """Stored qualification rows may predate write-side length limits."""

    kind: Literal["degree", "certificate"] = "certificate"
    title: str = Field(..., min_length=1)
    year: Optional[int] = None


class TherapistProfileBase(BaseModel):
    display_name: Optional[str] = Field(None, max_length=255)
    short_bio: Optional[str] = Field(None, max_length=2000)
    academic_qualifications: Optional[str] = Field(None, max_length=4000)
    academic_qualification_level: Optional[str] = Field(None, max_length=32)
    professional_certificates: list[str] = Field(default_factory=list)
    professional_qualification_entries: list[QualificationEntry] = Field(default_factory=list)
    services_offered: list[str] = Field(default_factory=list)


class TherapistProfileUpdate(TherapistProfileBase):
    supervisor_user_id: Optional[int] = None
    mentor_user_id: Optional[int] = None
    employment_start_date: Optional[date] = None
    leave_balance_year: Optional[int] = None
    leave_paid_days_backfill: Optional[int] = None
    leave_carry_forward_days_backfill: Optional[int] = None
    leave_backfill_note: Optional[str] = None
    tds_rate_percent: Optional[float] = Field(None, ge=0, le=100)


class TherapistProfileRead(TherapistProfileBase):
    # Read responses must tolerate legacy DB values longer than write limits.
    display_name: Optional[str] = None
    short_bio: Optional[str] = None
    academic_qualifications: Optional[str] = None
    academic_qualification_level: Optional[str] = None
    professional_qualification_entries: list[QualificationEntryRead] = Field(default_factory=list)

    id: Optional[int] = None
    user_id: int
    status: str
    admin_note: Optional[str] = None
    submitted_at: Optional[datetime] = None
    reviewed_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None
    email: Optional[str] = None
    full_name: Optional[str] = None
    supervisor_user_id: Optional[int] = None
    mentor_user_id: Optional[int] = None
    supervisor_name: Optional[str] = None
    mentor_name: Optional[str] = None
    employment_start_date: Optional[date] = None
    leave_balance_year: Optional[int] = None
    leave_paid_days_backfill: int = 0
    leave_carry_forward_days_backfill: int = 0
    leave_backfill_note: Optional[str] = None
    approved_snapshot: Optional[dict] = None
    pending_submission: Optional[dict] = None
    has_pending_changes: bool = False
    last_session_log_at: Optional[datetime] = None
    days_since_last_session_log: Optional[int] = None
    tds_rate_percent: Optional[float] = None
    quality: Optional[dict[str, Any]] = None

    model_config = {"from_attributes": True}


class TherapistProfileAdminCreate(TherapistProfileBase):
    user_id: int
    status: Optional[str] = "APPROVED"
    supervisor_user_id: Optional[int] = None
    mentor_user_id: Optional[int] = None
    employment_start_date: Optional[date] = None


class TherapistProfileReview(BaseModel):
    admin_note: Optional[str] = None


class TherapistProfileRequestChanges(BaseModel):
    admin_note: str = Field(..., min_length=8, max_length=2000)


class ProductModuleDef(BaseModel):
    id: str = Field(min_length=2, max_length=64)
    label: str = Field(min_length=2, max_length=255)


class ServiceCategoryRead(BaseModel):
    id: str
    label: str
    description: Optional[str] = None
    sort_order: int = 0
    is_active: bool = True
    product_modules: list[ProductModuleDef] = []


class ServiceCategoryCreate(BaseModel):
    id: Optional[str] = None
    label: str = Field(min_length=2, max_length=255)
    description: Optional[str] = None
    sort_order: int = 0
    product_modules: Optional[list[ProductModuleDef]] = None


class ServiceCategoryUpdate(BaseModel):
    label: Optional[str] = Field(default=None, min_length=2, max_length=255)
    description: Optional[str] = None
    sort_order: Optional[int] = None
    product_modules: Optional[list[ProductModuleDef]] = None
    is_active: Optional[bool] = None
