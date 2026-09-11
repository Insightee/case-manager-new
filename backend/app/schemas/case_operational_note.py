from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class CaseOperationalNoteCreate(BaseModel):
    heading: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1)


class CaseOperationalNoteRead(BaseModel):
    id: int
    case_id: int
    heading: str
    body: str
    author_user_id: Optional[int] = None
    author_name: Optional[str] = None
    is_legacy_import: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}
