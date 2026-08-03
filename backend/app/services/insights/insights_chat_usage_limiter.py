"""Weekly Insights Ask cap — 5 questions per case per therapist per week."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.ai_generation import AiGenerationLog

WEEKLY_ASK_CAP = 5
INSIGHTS_ASK_ACTION = "insights_ask"


def _week_start(now: datetime | None = None) -> datetime:
    now = now or datetime.now(timezone.utc)
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return start_of_day - timedelta(days=start_of_day.weekday())


def get_usage(db: Session, *, case_id: int, user_id: int, now: datetime | None = None) -> dict:
    week_start = _week_start(now)
    used = int(
        db.scalar(
            select(func.count())
            .select_from(AiGenerationLog)
            .where(
                AiGenerationLog.case_id == case_id,
                AiGenerationLog.user_id == user_id,
                AiGenerationLog.action == INSIGHTS_ASK_ACTION,
                AiGenerationLog.created_at >= week_start,
            )
        )
        or 0
    )
    resets_at = week_start + timedelta(days=7)
    return {
        "used": used,
        "cap": WEEKLY_ASK_CAP,
        "remaining": max(0, WEEKLY_ASK_CAP - used),
        "resets_at": resets_at.isoformat(),
    }
