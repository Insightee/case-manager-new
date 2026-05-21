from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class AdminIepSummary(BaseModel):
    total_cases: int
    missing: int
    internal_only: int
    awaiting_ack: int
    acknowledged: int


class AdminIepRow(BaseModel):
    case_id: int
    case_code: str
    child_name: Optional[str] = None
    service_type: str
    product_module: str
    case_status: str
    iep_status: str
    attachment_id: Optional[int] = None
    file_name: Optional[str] = None
    version: Optional[str] = None
    visibility_status: Optional[str] = None
    uploaded_at: Optional[str] = None
    uploaded_by_name: Optional[str] = None
    parent_contacts: list[str] = []


class AdminIepDashboard(BaseModel):
    summary: AdminIepSummary
    rows: list[AdminIepRow]
