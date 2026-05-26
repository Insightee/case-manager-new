from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field


PERFORMANCE_DOMAINS = (
    "academic",
    "social",
    "speech",
    "behavioral",
    "self_help",
    "motor",
    "sensory",
    "other",
)

LEARNING_STYLE_OPTIONS = ("visual", "auditory", "kinesthetic", "multimodal")


class LearningEnvironmentRow(BaseModel):
    environment: str = ""
    strengths: str = ""
    goals: str = ""
    strategies: str = ""
    supports_needed: str = ""


class IepHeaderSection(BaseModel):
    child_name: str = ""
    age_label: str = ""
    diagnosis: str = ""
    service_provided: str = ""
    parents_names: str = ""
    therapist_name: str = ""
    school_or_home_name: str = ""
    class_grade: str = ""
    date_of_evaluation: Optional[str] = None
    date_of_iep_meeting: Optional[str] = None
    review_date: Optional[str] = None
    about_child_brief: str = ""


class IepPerformanceDomain(BaseModel):
    domain: str = "academic"
    notes: str = ""


class IepLearningStyleSection(BaseModel):
    styles: list[str] = Field(default_factory=list)
    elaboration: str = ""


class IepGoalStrategyBlock(BaseModel):
    strengths: str = ""
    goals: str = ""
    strategies: str = ""
    areas_of_need: str = ""


class IepVerificationSection(BaseModel):
    therapist_verified: bool = False
    therapist_name: str = ""
    therapist_date: Optional[str] = None
    therapist_license_no: str = ""
    case_manager_name: str = ""
    case_manager_date: Optional[str] = None
    client_name: str = ""
    client_date: Optional[str] = None


class IepPlanSections(BaseModel):
    schema_version: int = 2
    header: IepHeaderSection = Field(default_factory=IepHeaderSection)
    observations: str = ""
    learning_environments: list[LearningEnvironmentRow] = Field(default_factory=list)
    challenges: str = ""
    current_performance: list[IepPerformanceDomain] = Field(default_factory=list)
    learning_style: IepLearningStyleSection = Field(default_factory=IepLearningStyleSection)
    interventions: str = ""
    talent_development: IepGoalStrategyBlock = Field(default_factory=IepGoalStrategyBlock)
    other_areas_of_need: IepGoalStrategyBlock = Field(default_factory=IepGoalStrategyBlock)
    intervention_by_insighte: str = ""
    verification: IepVerificationSection = Field(default_factory=IepVerificationSection)
    about_child: str = ""
    referral: str = ""
    signatures: str = ""


class IepPlanSuggestionRead(BaseModel):
    id: int
    author_user_id: int
    author_role: str
    author_name: Optional[str] = None
    body: str
    created_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None


class IepPlanRead(BaseModel):
    id: int
    case_id: int
    version: str
    status: str
    visibility_status: str
    sections: IepPlanSections
    case_context: Optional[dict] = None
    suggestions: list[IepPlanSuggestionRead] = Field(default_factory=list)
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


class IepPlanSuggestionCreate(BaseModel):
    body: str


class IepPlanListItem(BaseModel):
    id: int
    case_id: int
    case_code: Optional[str] = None
    child_name: Optional[str] = None
    version: str
    status: str
    visibility_status: str
    updated_at: Optional[datetime] = None
