"""Rate limits, budget guard, and context compression for AI preview."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select

from app.core.config import settings

DAILY_PREVIEW_LIMIT = 50
MAX_CONTEXT_CHARS = 4000
MAX_PER_USER_ACTION = 30
_WINDOW_MINUTES = 60
_COST_PER_1K_TOKENS_INR = 0.5

_LIMITS: dict[str, int] = defaultdict(int)
_WINDOW: dict[str, datetime] = {}


def compress_context(context: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in context.items():
        if isinstance(value, str) and len(value) > MAX_CONTEXT_CHARS:
            out[key] = value[:MAX_CONTEXT_CHARS] + "…"
        else:
            out[key] = value
    return out


def check_rate_limit(user_id: int, action: str) -> None:
    key = f"{user_id}:{action}"
    now = datetime.now(timezone.utc)
    started = _WINDOW.get(key)
    if not started or now - started > timedelta(minutes=_WINDOW_MINUTES):
        _WINDOW[key] = now
        _LIMITS[key] = 0
    _LIMITS[key] += 1
    if _LIMITS[key] > MAX_PER_USER_ACTION:
        raise HTTPException(status_code=429, detail="AI preview rate limit exceeded")


def within_daily_limit(count: int) -> bool:
    return count < DAILY_PREVIEW_LIMIT


def estimate_cost(input_tokens: int, output_tokens: int, provider: str) -> float:
    if provider == "mock":
        return 0.0
    total = input_tokens + output_tokens
    return round((total / 1000.0) * _COST_PER_1K_TOKENS_INR, 4)


def check_budget(db) -> None:
    if not settings.AI_ENABLED and settings.AI_PROVIDER != "mock":
        return
    daily_budget = float(settings.AI_DAILY_BUDGET_INR or 0)
    monthly_budget = float(settings.AI_MONTHLY_BUDGET_INR or 0)
    if daily_budget <= 0 and monthly_budget <= 0:
        return

    from app.models.ai_generation import AiGenerationLog

    now = datetime.now(timezone.utc)
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    if daily_budget > 0:
        day_count = int(
            db.scalar(
                select(func.count())
                .select_from(AiGenerationLog)
                .where(AiGenerationLog.created_at >= day_start)
            )
            or 0
        )
        day_est = day_count * _COST_PER_1K_TOKENS_INR * 2
        if day_est >= daily_budget:
            raise HTTPException(
                status_code=429,
                detail="AI generation is currently paused because budget limit was reached.",
            )

    if monthly_budget > 0:
        month_count = int(
            db.scalar(
                select(func.count())
                .select_from(AiGenerationLog)
                .where(AiGenerationLog.created_at >= month_start)
            )
            or 0
        )
        month_est = month_count * _COST_PER_1K_TOKENS_INR * 2
        if month_est >= monthly_budget:
            raise HTTPException(
                status_code=429,
                detail="AI budget limit reached. Please contact admin or use saved snapshots.",
            )
