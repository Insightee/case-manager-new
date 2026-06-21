"""Audit logging and cache lookup for AI preview generations."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.ai_generation import AiDraftOutput, AiGenerationLog
from app.services.ai_prompt_registry import PROMPT_VERSION


def find_cached(db: Session, *, action: str, input_hash: str) -> dict | None:
    cached = db.scalars(
        select(AiGenerationLog)
        .where(AiGenerationLog.input_hash == input_hash, AiGenerationLog.action == action)
        .order_by(AiGenerationLog.id.desc())
        .limit(1)
    ).first()
    if not cached:
        return None
    draft = db.scalars(
        select(AiDraftOutput)
        .where(AiDraftOutput.generation_log_id == cached.id)
        .order_by(AiDraftOutput.id.desc())
        .limit(1)
    ).first()
    if not draft:
        return None
    return {
        "draft_text": draft.draft_text,
        "log_id": cached.id,
        "draft_id": draft.id,
        "cached": True,
        "prompt_version": PROMPT_VERSION,
    }


def count_previews_today(db: Session, user_id: int) -> int:
    start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    return int(
        db.scalar(
            select(func.count())
            .select_from(AiGenerationLog)
            .where(AiGenerationLog.user_id == user_id, AiGenerationLog.created_at >= start)
        )
        or 0
    )


def record_generation(
    db: Session,
    *,
    user_id: int,
    case_id: int | None,
    action: str,
    provider: str,
    model: str | None,
    input_hash: str,
    draft_text: str,
    target_type: str,
    target_id: int | None,
) -> dict:
    log = AiGenerationLog(
        user_id=user_id,
        case_id=case_id,
        action=action,
        provider=provider,
        model=model,
        input_hash=input_hash,
        token_count=len(draft_text.split()),
        cached=False,
    )
    db.add(log)
    db.flush()
    out = AiDraftOutput(
        generation_log_id=log.id,
        target_type=target_type,
        target_id=target_id,
        draft_text=draft_text,
        accepted=False,
    )
    db.add(out)
    db.commit()
    db.refresh(out)
    return {
        "draft_text": draft_text,
        "log_id": log.id,
        "draft_id": out.id,
        "cached": False,
        "prompt_version": PROMPT_VERSION,
    }
