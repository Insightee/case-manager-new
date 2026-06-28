"""Parent goal input capture — reviewable, never auto-mutates IEP."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.case import Case
from app.models.parent_goal_input import ParentGoalInput
from app.models.user import User
from app.services.clinical_review_queue_service import ensure_queue_item_for_parent_input

INPUT_TYPES = frozenset(
    {
        "see_at_home",
        "hard_at_home",
        "strategy_helps",
        "strategy_not_fit",
        "team_consider",
        "free_comment",
    }
)


def create_parent_goal_input(
    db: Session,
    *,
    case: Case,
    user: User,
    goal_ref: str,
    input_type: str,
    comment: str | None = None,
) -> dict[str, Any]:
    if input_type not in INPUT_TYPES:
        raise HTTPException(status_code=400, detail="Invalid input type")

    row = ParentGoalInput(
        case_id=case.id,
        goal_ref=goal_ref,
        input_type=input_type,
        comment=(comment or "").strip() or None,
        parent_user_id=user.id,
        review_status="pending",
    )
    db.add(row)
    db.flush()
    ensure_queue_item_for_parent_input(
        db,
        row.id,
        case.id,
        title="Parent goal input",
        summary=comment or input_type.replace("_", " "),
        user_id=user.id,
    )
    db.commit()
    db.refresh(row)
    return {
        "id": row.id,
        "goal_ref": row.goal_ref,
        "input_type": row.input_type,
        "comment": row.comment,
        "review_status": row.review_status,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }
