from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class LearningEnvironmentRow(BaseModel):
    environment: str = ""
    strengths: str = ""
    supports_needed: str = ""


class IepPlanSections(BaseModel):
    about_child: str = ""
    referral: str = ""
    observations: str = ""
    learning_environments: list[LearningEnvironmentRow] = Field(default_factory=list)
    interventions: str = ""
    signatures: str = ""


class IepPlanRead(BaseModel):
    id: int
    case_id: int
    version: str
    status: str
    visibility_status: str
    sections: IepPlanSections
    attachment_id: Optional[int] = None
    created_by_user_id: int
    published_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    can_edit: bool = False
    can_share_with_parent: bool = False


class IepPlanSave(BaseModel):
    sections: IepPlanSections
    version: Optional[str] = None


class IepPlanListItem(BaseModel):
    id: int
    case_id: int
    case_code: Optional[str] = None
    child_name: Optional[str] = None
    version: str
    status: str
    visibility_status: str
    updated_at: Optional[datetime] = None
