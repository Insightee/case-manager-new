from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class CaseZohoIdBulkRow(BaseModel):
    case_code: Optional[str] = Field(None, max_length=32)
    zoho_id: Optional[str] = Field(None, max_length=64)


class CaseZohoIdBulkRequest(BaseModel):
    rows: list[CaseZohoIdBulkRow] = Field(min_length=1, max_length=1000)
    apply: bool = False


class CaseZohoIdBulkRowResult(BaseModel):
    row_index: int
    case_code: Optional[str] = None
    zoho_id: Optional[str] = None
    old_zoho_id: Optional[str] = None
    status: str
    message: Optional[str] = None
    warning: Optional[str] = None


class CaseZohoIdBulkResponse(BaseModel):
    apply: bool
    summary: dict
    results: list[CaseZohoIdBulkRowResult]
