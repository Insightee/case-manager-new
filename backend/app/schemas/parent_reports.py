from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class ParentReportCommentCreate(BaseModel):
    body: str = Field(min_length=1)
    comment_type: Literal["GENERAL", "GOAL_SUGGESTION", "CHANGE_REQUEST"] = "GENERAL"


class ParentMonthlyFeedback(BaseModel):
    message: str = Field(min_length=1)
    comment_type: Optional[str] = None
