from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel


class TherapistSessionReviewRead(BaseModel):
    id: int
    rating: Optional[int] = None
    feedback: Optional[str] = None
    feedback_at: Optional[datetime] = None
    is_public: bool = False
    scheduled_date: Optional[date] = None
    child_name: Optional[str] = None
    case_code: Optional[str] = None


class TherapistReviewSummary(BaseModel):
    total_count: int = 0
    public_count: int = 0
    average_rating: Optional[float] = None
    public_average_rating: Optional[float] = None


class TherapistReviewsResponse(BaseModel):
    summary: TherapistReviewSummary
    reviews: list[TherapistSessionReviewRead]
