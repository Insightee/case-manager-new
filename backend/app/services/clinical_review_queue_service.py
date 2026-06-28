"""Unified clinical review queue — heterogeneous items with audit trail."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.clinical_review_queue import ClinicalReviewQueueEvent, ClinicalReviewQueueItem
from app.models.goal_repository import GoalRepositoryItem, StrategyRepositoryItem
from app.models.strategy_recommendation_feedback import StrategyRecommendationFeedback
from app.models.user import User
from app.services import goal_repository_service as repo_svc

ACTION_STATUS_MAP = {
    "approve": "approved",
    "merge": "merged",
    "request_revision": "revision_requested",
    "mark_case_specific": "case_specific",
    "reject": "rejected",
    "close": "closed",
}


def _dump(payload: dict[str, Any] | None) -> str | None:
    return json.dumps(payload, default=str) if payload else None


def _item_dict(row: ClinicalReviewQueueItem) -> dict[str, Any]:
    return {
        "id": row.id,
        "item_type": row.item_type,
        "status": row.status,
        "priority": row.priority,
        "source_case_id": row.source_case_id,
        "source_goal_id": row.source_goal_id,
        "source_strategy_id": row.source_strategy_id,
        "linked_library_goal_id": row.linked_library_goal_id,
        "linked_library_strategy_id": row.linked_library_strategy_id,
        "title": row.title,
        "summary": row.summary,
        "reviewer_note": row.reviewer_note,
        "parent_safe": row.parent_safe,
        "assigned_to_user_id": row.assigned_to_user_id,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "resolved_at": row.resolved_at.isoformat() if row.resolved_at else None,
    }


def _record_event(
    db: Session,
    *,
    item: ClinicalReviewQueueItem,
    actor_user_id: int,
    old_status: str | None,
    new_status: str,
    action: str,
    note: str | None = None,
    payload: dict[str, Any] | None = None,
) -> None:
    db.add(
        ClinicalReviewQueueEvent(
            queue_item_id=item.id,
            actor_user_id=actor_user_id,
            old_status=old_status,
            new_status=new_status,
            action=action,
            note=note,
            payload_json=_dump(payload),
        )
    )


def ensure_queue_item_for_feedback(db: Session, feedback: StrategyRecommendationFeedback, user: User) -> ClinicalReviewQueueItem:
    existing = db.scalars(
        select(ClinicalReviewQueueItem).where(
            ClinicalReviewQueueItem.item_type == "recommendation_feedback",
            ClinicalReviewQueueItem.source_entity_kind == "strategy_recommendation_feedback",
            ClinicalReviewQueueItem.source_entity_id == feedback.id,
            ClinicalReviewQueueItem.status.in_(("pending", "in_review", "revision_requested")),
        )
    ).first()
    if existing:
        return existing
    item = ClinicalReviewQueueItem(
        item_type="recommendation_feedback",
        status="pending",
        priority="normal",
        source_case_id=feedback.case_id,
        source_strategy_id=feedback.strategy_repository_item_id,
        source_entity_kind="strategy_recommendation_feedback",
        source_entity_id=feedback.id,
        title="Strategy recommendation needs CM input",
        summary=feedback.adaptation_text or feedback.dismissal_reason,
    )
    db.add(item)
    db.flush()
    _record_event(
        db,
        item=item,
        actor_user_id=user.id,
        old_status=None,
        new_status="pending",
        action="create",
        note="Created from recommendation feedback",
    )
    return item


def ensure_queue_item_for_parent_input(db: Session, parent_input_id: int, case_id: int, title: str, summary: str, user_id: int) -> ClinicalReviewQueueItem:
    item = ClinicalReviewQueueItem(
        item_type="parent_goal_suggestion",
        status="pending",
        priority="normal",
        source_case_id=case_id,
        source_entity_kind="parent_goal_input",
        source_entity_id=parent_input_id,
        title=title,
        summary=summary,
    )
    db.add(item)
    db.flush()
    _record_event(
        db,
        item=item,
        actor_user_id=user_id,
        old_status=None,
        new_status="pending",
        action="create",
    )
    return item


def list_queue_items(
    db: Session,
    *,
    status: str | None = None,
    item_type: str | None = None,
    priority: str | None = None,
    case_id: int | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    q = select(ClinicalReviewQueueItem).order_by(ClinicalReviewQueueItem.id.desc()).limit(limit)
    if status:
        q = q.where(ClinicalReviewQueueItem.status == status)
    if item_type:
        q = q.where(ClinicalReviewQueueItem.item_type == item_type)
    if priority:
        q = q.where(ClinicalReviewQueueItem.priority == priority)
    if case_id:
        q = q.where(ClinicalReviewQueueItem.source_case_id == case_id)
    return [_item_dict(r) for r in db.scalars(q).all()]


def apply_queue_action(
    db: Session,
    *,
    item_id: int,
    actor: User,
    action: str,
    reviewer_note: str | None = None,
    linked_library_goal_id: int | None = None,
    linked_library_strategy_id: int | None = None,
    revision_request: str | None = None,
    parent_safe: bool = False,
) -> dict[str, Any]:
    item = db.get(ClinicalReviewQueueItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Queue item not found")

    if action not in ACTION_STATUS_MAP:
        raise HTTPException(status_code=400, detail="Invalid action")

    if action in ("reject", "request_revision") and not (reviewer_note or revision_request):
        raise HTTPException(status_code=400, detail="A reviewer note is needed for this action")

    if action == "merge" and not (linked_library_goal_id or linked_library_strategy_id):
        raise HTTPException(status_code=400, detail="Merge requires a linked library goal or strategy")

    old_status = item.status
    new_status = ACTION_STATUS_MAP[action]
    item.status = new_status
    item.reviewer_user_id = actor.id
    item.reviewer_note = reviewer_note or revision_request
    item.parent_safe = parent_safe
    item.linked_library_goal_id = linked_library_goal_id
    item.linked_library_strategy_id = linked_library_strategy_id
    item.resolved_at = datetime.now(timezone.utc)

    if item.item_type in ("custom_goal", "goal_candidates") and item.source_entity_id and action == "approve":
        repo_svc.review_goal_item(
            db,
            item.source_entity_id,
            action="approve_case",
            actor_user_id=actor.id,
            note=reviewer_note,
        )
    elif item.item_type in ("custom_strategy", "strategy_candidates") and item.source_entity_id and action == "approve":
        repo_svc.review_strategy_item(
            db,
            item.source_entity_id,
            action="approve_case",
            actor_user_id=actor.id,
            note=reviewer_note,
        )
    elif item.item_type == "custom_goal" and action == "merge" and linked_library_goal_id and item.source_entity_id:
        repo_svc.review_goal_item(
            db,
            item.source_entity_id,
            action="merge",
            actor_user_id=actor.id,
            note=reviewer_note,
            merged_into_id=linked_library_goal_id,
        )
    elif item.item_type == "custom_strategy" and action == "merge" and linked_library_strategy_id and item.source_entity_id:
        repo_svc.review_strategy_item(
            db,
            item.source_entity_id,
            action="merge",
            actor_user_id=actor.id,
            note=reviewer_note,
            merged_into_id=linked_library_strategy_id,
        )

    _record_event(
        db,
        item=item,
        actor_user_id=actor.id,
        old_status=old_status,
        new_status=new_status,
        action=action,
        note=reviewer_note or revision_request,
        payload={
            "linked_library_goal_id": linked_library_goal_id,
            "linked_library_strategy_id": linked_library_strategy_id,
            "parent_safe": parent_safe,
        },
    )
    db.commit()
    db.refresh(item)
    return _item_dict(item)


def sync_repository_candidates_to_queue(db: Session, limit: int = 50) -> int:
    """Idempotently surface pending repository items in unified queue."""
    created = 0
    for row in db.scalars(
        select(GoalRepositoryItem).where(GoalRepositoryItem.status.in_(("local", "candidate"))).limit(limit)
    ).all():
        exists = db.scalars(
            select(ClinicalReviewQueueItem).where(
                ClinicalReviewQueueItem.item_type == "custom_goal",
                ClinicalReviewQueueItem.source_entity_kind == "goal_repository_item",
                ClinicalReviewQueueItem.source_entity_id == row.id,
            )
        ).first()
        if exists:
            continue
        db.add(
            ClinicalReviewQueueItem(
                item_type="custom_goal",
                status="pending",
                source_case_id=row.case_id or 0,
                source_goal_id=row.id,
                source_entity_kind="goal_repository_item",
                source_entity_id=row.id,
                title=row.label,
                summary=row.rationale,
            )
        )
        created += 1
    for row in db.scalars(
        select(StrategyRepositoryItem).where(StrategyRepositoryItem.status.in_(("local", "candidate"))).limit(limit)
    ).all():
        exists = db.scalars(
            select(ClinicalReviewQueueItem).where(
                ClinicalReviewQueueItem.item_type == "custom_strategy",
                ClinicalReviewQueueItem.source_entity_kind == "strategy_repository_item",
                ClinicalReviewQueueItem.source_entity_id == row.id,
            )
        ).first()
        if exists:
            continue
        db.add(
            ClinicalReviewQueueItem(
                item_type="custom_strategy",
                status="pending",
                source_case_id=row.case_id or 0,
                source_strategy_id=row.id,
                source_entity_kind="strategy_repository_item",
                source_entity_id=row.id,
                title=row.label,
                summary=row.when_to_use,
            )
        )
        created += 1
    if created:
        db.commit()
    return created
