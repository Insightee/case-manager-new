"""Case-scoped Insights Ask — explicit user question only, compact context."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.clinical_snapshot import ClinicalSnapshot
from app.models.user import User
from app.services import ai_audit_service, ai_gateway_service as ai_svc
from app.services.insights import insights_chat_usage_limiter as ask_limiter
from app.services.insights.ai_insight_refresh_service import INSIGHT_REFRESH_TYPE, compact_ai_context
from app.services.insights.case_insight_aggregator import build_case_insight_payload

CAP_EXCEEDED_MESSAGE = (
    "You've reached this week's ask limit for this case. Weekly insights still update from session logs "
    "— try again next week."
)


def _latest_refresh_text(db: Session, *, case_id: int) -> str:
    snap = db.scalars(
        select(ClinicalSnapshot)
        .where(
            ClinicalSnapshot.case_id == case_id,
            ClinicalSnapshot.insight_type == INSIGHT_REFRESH_TYPE,
        )
        .order_by(ClinicalSnapshot.id.desc())
        .limit(1)
    ).first()
    if not snap:
        return ""
    return (snap.ai_output_text or "").strip()


def ask_insight(
    db: Session,
    *,
    case_id: int,
    user: User,
    question: str,
) -> dict[str, Any]:
    q = (question or "").strip()
    if not q:
        raise ValueError("Add a question before sending.")

    usage = ask_limiter.get_usage(db, case_id=case_id, user_id=user.id)
    if usage["remaining"] <= 0:
        return {
            "answer": None,
            "provider": None,
            "usage": usage,
            "capExceeded": True,
            "message": CAP_EXCEEDED_MESSAGE,
            "sources_hint": "Session logs, IEP goals, and structured insights",
        }

    payload = build_case_insight_payload(db, case_id)
    context = compact_ai_context(payload)
    refresh_text = _latest_refresh_text(db, case_id=case_id)

    gen = ai_svc.AIGatewayService.answer_snapshot_followup(
        db,
        user_id=user.id,
        case_id=case_id,
        question=q,
        snapshot_text=refresh_text,
        context=context,
    )

    input_hash = ai_svc.AIGatewayService.input_hash_for_payload(
        {"question": q, "context": context, "refresh": refresh_text[:500]}
    )
    log_result = ai_audit_service.record_generation(
        db,
        user_id=user.id,
        case_id=case_id,
        action=ask_limiter.INSIGHTS_ASK_ACTION,
        provider=gen.get("provider") or "mock",
        model=gen.get("model"),
        input_hash=input_hash,
        draft_text=gen.get("answer") or "",
        target_type="insights_ask",
        target_id=case_id,
    )

    updated_usage = ask_limiter.get_usage(db, case_id=case_id, user_id=user.id)
    return {
        "answer": gen.get("answer"),
        "provider": gen.get("provider"),
        "usage": updated_usage,
        "capExceeded": False,
        "generation_log_id": log_result.get("log_id"),
        "sources_hint": "Session logs, IEP goals, and structured insights",
    }
