"""Rule-based IEP review suggestions from goal coverage gaps."""

from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.iep_review_suggestion import IepReviewSuggestion, IepReviewSuggestionStatus
from app.services import clinical_workbench_service as wb_svc
from app.services import goal_repository_service as repo_svc


def list_suggestions(db: Session, case_id: int, *, include_resolved: bool = False) -> dict:
    existing = db.scalars(
        select(IepReviewSuggestion)
        .where(IepReviewSuggestion.case_id == case_id)
        .order_by(IepReviewSuggestion.id.desc())
    ).all()
    if not existing:
        summary = wb_svc.build_clinical_quality_summary(db, case_id)
        for g in summary.get("goal_coverage", []):
            if g.get("stale"):
                db.add(
                    IepReviewSuggestion(
                        case_id=case_id,
                        suggestion_type="stale_goal",
                        reason=f"Goal lacks recent session evidence: {g.get('label', '')[:120]}",
                        supporting_evidence_json=json.dumps(
                            {"sessions_addressed": g.get("sessions_addressed", 0)}
                        ),
                        confidence="moderate",
                        status=IepReviewSuggestionStatus.DRAFT.value,
                    )
                )
        db.flush()
        existing = db.scalars(
            select(IepReviewSuggestion)
            .where(IepReviewSuggestion.case_id == case_id)
            .order_by(IepReviewSuggestion.id.desc())
        ).all()

    items = [_row_dict(r) for r in existing]
    if not include_resolved:
        items = [
            i
            for i in items
            if i["status"]
            not in (
                IepReviewSuggestionStatus.DISMISSED.value,
                IepReviewSuggestionStatus.CONVERTED_TO_GOAL.value,
                IepReviewSuggestionStatus.CONVERTED_TO_STRATEGY.value,
            )
        ]
    return {"items": items}


def dismiss_suggestion(db: Session, case_id: int, suggestion_id: int, user_id: int) -> dict:
    row = db.get(IepReviewSuggestion, suggestion_id)
    if not row or row.case_id != case_id:
        raise ValueError("Suggestion not found")
    row.status = IepReviewSuggestionStatus.DISMISSED.value
    row.dismissed_reason = f"Dismissed by user {user_id}"
    db.flush()
    return _row_dict(row)


def accept_suggestion(db: Session, case_id: int, suggestion_id: int, user_id: int) -> dict:
    row = db.get(IepReviewSuggestion, suggestion_id)
    if not row or row.case_id != case_id:
        raise ValueError("Suggestion not found")
    label = row.reason.replace("Goal lacks recent session evidence: ", "")[:500]
    candidate = repo_svc.create_goal_candidate(
        db,
        case_id=case_id,
        user_id=user_id,
        domain_key="academics_learning",
        label=label or "Review suggested goal",
        rationale="Accepted from IEP review suggestion",
    )
    row.status = IepReviewSuggestionStatus.CONVERTED_TO_GOAL.value
    db.flush()
    out = _row_dict(row)
    out["goal_candidate"] = candidate
    return out


def create_suggestion_from_ai(
    db: Session,
    *,
    case_id: int,
    user_id: int,
    suggestion_type: str,
    reason: str,
    goal_title: str | None = None,
) -> dict:
    row = IepReviewSuggestion(
        case_id=case_id,
        suggestion_type=suggestion_type,
        reason=reason or f"AI suggestion for {goal_title or 'goal'}",
        supporting_evidence_json=json.dumps({"goal_title": goal_title, "source": "insights_engine"}),
        confidence="moderate",
        status=IepReviewSuggestionStatus.DRAFT.value,
        created_by_user_id=user_id,
    )
    db.add(row)
    db.flush()
    return _row_dict(row)


def _row_dict(row: IepReviewSuggestion) -> dict:
    return {
        "id": row.id,
        "case_id": row.case_id,
        "suggestion_type": row.suggestion_type,
        "reason": row.reason,
        "confidence": row.confidence,
        "status": row.status,
        "dismissed_reason": row.dismissed_reason,
    }
