from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class AdminCasePipelineCard(BaseModel):
    id: int
    case_code: str
    child_id: Optional[int] = None
    child_name: Optional[str] = None
    service_type: str
    product_module: str
    status: str
    pipeline_column: str
    case_manager_user_id: Optional[int] = None
    case_manager_name: Optional[str] = None
    therapist_user_id: Optional[int] = None
    therapist_name: Optional[str] = None
    assignment_end_date: Optional[str] = None
    created_at: Optional[str] = None
    operational_stage: Optional[str] = None
    reports_under_review: int = 0
    missing_logs: int = 0
    has_iep: bool = False
    iep_acknowledged: bool = False
    open_tickets: int = 0
    open_incidents: int = 0
    next_action: Optional[str] = None


class AdminCasePipelineColumn(BaseModel):
    id: str
    title: str
    tone: str
    count: int
    cases: list[AdminCasePipelineCard]


class AdminCasePipelineBoard(BaseModel):
    columns: list[AdminCasePipelineColumn]
    total_cases: int
