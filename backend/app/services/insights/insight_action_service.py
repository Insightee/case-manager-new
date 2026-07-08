"""Staging insight selections into the exception/review queue — never writes report text directly."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.case_insight_action import CaseInsightAction, InsightActionStatus

VALID_DESTINATIONS = frozenset({"monthly_report", "iep_review"})


def stage_insights_for_review(
    db: Session,
    *,
    case_id: int,
    user_id: int,
    insight_ids: list[str],
    destination: str,
    insights_by_id: dict[str, dict[str, Any]],
) -> list[CaseInsightAction]:
    if destination not in VALID_DESTINATIONS:
        raise ValueError(f"Invalid destination: {destination}")

    rows: list[CaseInsightAction] = []
    for insight_id in insight_ids:
        insight = insights_by_id.get(insight_id)
        if not insight:
            continue
        row = CaseInsightAction(
            case_id=case_id,
            insight_id=insight_id,
            insight_snapshot_json=json.dumps(insight, default=str),
            destination=destination,
            status=InsightActionStatus.PENDING_REVIEW.value,
            created_by_user_id=user_id,
        )
        db.add(row)
        rows.append(row)
    db.commit()
    for row in rows:
        db.refresh(row)
    return rows


def action_to_dict(row: CaseInsightAction) -> dict[str, Any]:
    try:
        snapshot = json.loads(row.insight_snapshot_json)
    except json.JSONDecodeError:
        snapshot = None
    return {
        "id": row.id,
        "caseId": row.case_id,
        "insightId": row.insight_id,
        "destination": row.destination,
        "status": row.status,
        "insight": snapshot,
        "createdAt": row.created_at.isoformat() if row.created_at else None,
    }


def list_actions_for_case(db: Session, case_id: int) -> list[dict[str, Any]]:
    rows = db.scalars(
        select(CaseInsightAction).where(CaseInsightAction.case_id == case_id).order_by(CaseInsightAction.id.desc())
    ).all()
    return [action_to_dict(r) for r in rows]
