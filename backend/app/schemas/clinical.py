from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field


class ClinicalProfileRead(BaseModel):
    case_id: int
    history: Optional[str] = None
    diagnosis: Optional[str] = None
    strengths: Optional[str] = None
    interests: Optional[str] = None
    goals_summary: Optional[str] = None
    updated_at: Optional[datetime] = None


class ClinicalProfileUpdate(BaseModel):
    history: Optional[str] = None
    diagnosis: Optional[str] = None
    strengths: Optional[str] = None
    interests: Optional[str] = None
    goals_summary: Optional[str] = None


class ObservationSectionDef(BaseModel):
    key: str
    label: str


class ObservationChecklistRead(BaseModel):
    id: int
    case_id: int
    therapist_user_id: int
    status: str
    sections: list[ObservationSectionDef]
    responses: dict[str, str] = Field(default_factory=dict)
    due_at: Optional[date] = None
    due_rule: Optional[str] = None
    is_due: bool = False
    is_overdue: bool = False
    submitted_at: Optional[datetime] = None
    reviewer_comment: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    observation_report_id: Optional[int] = None
    can_edit: bool = False
    can_submit: bool = False


class ObservationChecklistSave(BaseModel):
    responses: dict[str, str] = Field(default_factory=dict)
    sync_clinical_profile: bool = True


class ObservationChecklistReview(BaseModel):
    comment: Optional[str] = None
    share_with_parent: bool = True


class AdminObservationChecklistItem(BaseModel):
    id: int
    case_id: int
    case_code: Optional[str] = None
    child_name: Optional[str] = None
    therapist_name: Optional[str] = None
    status: str
    due_at: Optional[date] = None
    submitted_at: Optional[datetime] = None
    is_overdue: bool = False
