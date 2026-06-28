"""Strategy recommendation feedback — structured learning without auto pool mutation."""

from __future__ import annotations

import json
from typing import Any, Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.case import Case
from app.models.strategy_recommendation_feedback import FeedbackStatus, StrategyRecommendationFeedback
from app.models.user import User
from app.services.clinical_review_queue_service import ensure_queue_item_for_feedback

VALID_STATUSES = {s.value for s in FeedbackStatus}


def _dump_ctx(ctx: dict[str, Any] | None) -> str | None:
    if not ctx:
        return None
    return json.dumps(ctx, default=str)


def _row_dict(row: StrategyRecommendationFeedback) -> dict[str, Any]:
    return {
        "id": row.id,
        "case_id": row.case_id,
        "goal_repository_item_id": row.goal_repository_item_id,
        "goal_card_id": row.goal_card_id,
        "strategy_repository_item_id": row.strategy_repository_item_id,
        "recommendation_source": row.recommendation_source,
        "feedback_status": row.feedback_status,
        "adaptation_text": row.adaptation_text,
        "dismissal_reason": row.dismissal_reason,
        "created_by_user_id": row.created_by_user_id,
        "created_by_role": row.created_by_role,
        "parent_visible": row.parent_visible,
        "review_status": row.review_status,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _user_role_name(user: User) -> Optional[str]:
    if hasattr(user, "role_name") and user.role_name:
        return user.role_name
    if getattr(user, "roles", None):
        return user.roles[0].name
    return None


def create_feedback(
    db: Session,
    *,
    case: Case,
    user: User,
    payload: dict[str, Any],
) -> dict[str, Any]:
    status_val = payload.get("feedback_status")
    if status_val not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid feedback_status")

    if status_val == FeedbackStatus.ADAPTED.value and not (payload.get("adaptation_text") or "").strip():
        raise HTTPException(status_code=400, detail="Adaptation text is helpful when marking adapted")

    row = StrategyRecommendationFeedback(
        case_id=case.id,
        child_id=case.child_id,
        goal_repository_item_id=payload.get("goal_repository_item_id"),
        goal_card_id=payload.get("goal_card_id"),
        strategy_repository_item_id=payload.get("strategy_repository_item_id"),
        recommendation_source=payload.get("recommendation_source") or "library_match",
        feedback_status=status_val,
        adaptation_text=(payload.get("adaptation_text") or "").strip() or None,
        dismissal_reason=(payload.get("dismissal_reason") or "").strip() or None,
        created_by_user_id=user.id,
        created_by_role=_user_role_name(user),
        source_context_json=_dump_ctx(payload.get("source_context")),
        parent_visible=False,
        review_status="pending_review" if status_val == FeedbackStatus.NEEDS_CM_INPUT.value else None,
    )
    db.add(row)
    db.flush()

    if status_val == FeedbackStatus.NEEDS_CM_INPUT.value:
        ensure_queue_item_for_feedback(db, row, user)

    db.commit()
    db.refresh(row)
    return _row_dict(row)


def patch_feedback(
    db: Session,
    *,
    feedback_id: int,
    case: Case,
    user: User,
    payload: dict[str, Any],
) -> dict[str, Any]:
    row = db.get(StrategyRecommendationFeedback, feedback_id)
    if not row or row.case_id != case.id:
        raise HTTPException(status_code=404, detail="Feedback not found")
    if row.created_by_user_id != user.id:
        from app.core.permissions import user_has_permission

        if not user_has_permission(user, "case.read.all") and not user_has_permission(user, "case.read.team"):
            raise HTTPException(status_code=403, detail="Cannot edit this feedback")

    if "feedback_status" in payload:
        st = payload["feedback_status"]
        if st not in VALID_STATUSES:
            raise HTTPException(status_code=400, detail="Invalid feedback_status")
        row.feedback_status = st
        if st == FeedbackStatus.NEEDS_CM_INPUT.value:
            row.review_status = "pending_review"
            ensure_queue_item_for_feedback(db, row, user)
    if "adaptation_text" in payload:
        row.adaptation_text = (payload["adaptation_text"] or "").strip() or None
    if "dismissal_reason" in payload:
        row.dismissal_reason = (payload["dismissal_reason"] or "").strip() or None

    db.commit()
    db.refresh(row)
    return _row_dict(row)


def list_feedback_for_case(
    db: Session,
    case_id: int,
    *,
    goal_repository_item_id: int | None = None,
    goal_card_id: int | None = None,
    strategy_repository_item_id: int | None = None,
) -> list[dict[str, Any]]:
    q = select(StrategyRecommendationFeedback).where(StrategyRecommendationFeedback.case_id == case_id)
    if goal_repository_item_id:
        q = q.where(StrategyRecommendationFeedback.goal_repository_item_id == goal_repository_item_id)
    if goal_card_id:
        q = q.where(StrategyRecommendationFeedback.goal_card_id == goal_card_id)
    if strategy_repository_item_id:
        q = q.where(StrategyRecommendationFeedback.strategy_repository_item_id == strategy_repository_item_id)
    rows = db.scalars(q.order_by(StrategyRecommendationFeedback.id.desc()).limit(200)).all()
    return [_row_dict(r) for r in rows]
