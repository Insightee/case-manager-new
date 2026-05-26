from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class CmCaseloadRow(BaseModel):
    id: int
    case_code: str
    child_name: Optional[str] = None
    service_type: str
    product_module: str
    status: str
    therapist_name: Optional[str] = None
    pipeline_column: Optional[str] = None
    next_action: Optional[str] = None
    open_reports: int = 0
    missing_logs: int = 0
    open_tickets: int = 0
    open_incidents: int = 0
    href: str


class CmCaseloadSummary(BaseModel):
    total: int = 0
    active: int = 0
    pending_allotment: int = 0
    needs_action: int = 0
    suspended: int = 0


class CmWorkbenchSection(BaseModel):
    count: int = 0
    items: list[dict[str, Any]] = Field(default_factory=list)


class AdminCmHomeResponse(BaseModel):
    role: str = "CASE_MANAGER"
    landing_route: str = "/admin/cm"
    caseload_summary: CmCaseloadSummary
    caseload: list[CmCaseloadRow]
    sections: dict[str, CmWorkbenchSection]
    quick_actions: list[dict[str, str]]
