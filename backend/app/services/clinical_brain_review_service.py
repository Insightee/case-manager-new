"""Clinical Brain admin review queue — wraps repository review actions."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.case import Case
from app.models.clinical_report import ClinicalReport, ClinicalReportStatus
from app.models.goal_repository import GoalRepositoryItem, RepositoryItemStatus, StrategyRepositoryItem
from app.models.report import MonthlyReport, ReportStatus
from app.services import goal_repository_service as repo_svc
from app.services.goals_engine_service import (
    _goal_row_dict,
    _strategy_row_dict,
    list_admin_goal_strategy_repository,
)

ACTION_ALIASES = {
    "approve_for_case": "approve_case",
    "return_with_comment": "request_edits",
    "send_to_bank": "approve_pool",
}


def _normalize_action(action: str) -> str:
    return ACTION_ALIASES.get(action, action)



def list_clinical_review_queue(db: Session, *, tab: str = "goal_candidates", limit: int = 100) -> dict[str, Any]:
    base = list_admin_goal_strategy_repository(db, limit=limit)
    pending_statuses = (RepositoryItemStatus.LOCAL.value, RepositoryItemStatus.CANDIDATE.value)

    returned_goals = db.scalars(
        select(GoalRepositoryItem)
        .where(
            GoalRepositoryItem.review_note.isnot(None),
            GoalRepositoryItem.status.in_(pending_statuses),
        )
        .order_by(GoalRepositoryItem.id.desc())
        .limit(limit)
    ).all()
    returned_strategies = db.scalars(
        select(StrategyRepositoryItem)
        .where(
            StrategyRepositoryItem.review_note.isnot(None),
            StrategyRepositoryItem.status.in_(pending_statuses),
        )
        .order_by(StrategyRepositoryItem.id.desc())
        .limit(limit)
    ).all()

    def _case_meta(row: GoalRepositoryItem | StrategyRepositoryItem) -> dict[str, Any]:
        d = _goal_row_dict(db, row) if isinstance(row, GoalRepositoryItem) else _strategy_row_dict(db, row)
        if row.case_id:
            case = db.get(Case, row.case_id)
            d["case_code"] = case.case_code if case else None
            d["child_name"] = case.child.full_name if case and case.child else None
        return d

    reports_clinical = db.scalars(
        select(ClinicalReport)
        .where(ClinicalReport.status == ClinicalReportStatus.SUBMITTED_FOR_REVIEW.value)
        .order_by(ClinicalReport.id.desc())
        .limit(limit)
    ).all()
    reports_monthly = db.scalars(
        select(MonthlyReport)
        .where(MonthlyReport.status == ReportStatus.UNDER_REVIEW)
        .order_by(MonthlyReport.id.desc())
        .limit(limit)
    ).all()

    payload: dict[str, Any] = {
        "tab": tab,
        "pending_goals": base["pending_goals"],
        "pending_strategies": base["pending_strategies"],
        "returned_items": [_case_meta(g) for g in returned_goals] + [_case_meta(s) for s in returned_strategies],
        "missing_evidence": [],
        "language_flags": [],
        "missing_evidence_placeholder": True,
        "language_flags_placeholder": True,
        "reports_needing_review": [
            {
                "id": r.id,
                "case_id": r.case_id,
                "report_type": r.report_type,
                "status": r.status,
            }
            for r in reports_clinical
        ]
        + [
            {
                "id": r.id,
                "case_id": r.case_id,
                "report_type": "monthly",
                "status": r.status.value if hasattr(r.status, "value") else r.status,
            }
            for r in reports_monthly
        ],
    }
    if tab == "returned":
        payload["items"] = payload["returned_items"]
    elif tab == "strategy_candidates":
        payload["items"] = payload["pending_strategies"]
    elif tab == "goal_candidates":
        payload["items"] = payload["pending_goals"]
    else:
        payload["items"] = []
    return payload


def apply_review_queue_action(
    db: Session,
    *,
    kind: str,
    item_id: int,
    action: str,
    actor_user_id: int,
    note: str | None = None,
    merged_into_id: int | None = None,
) -> dict | None:
    normalized = _normalize_action(action)
    if kind == "goal":
        return repo_svc.review_goal_item(
            db,
            item_id,
            action=normalized,
            actor_user_id=actor_user_id,
            note=note,
            merged_into_id=merged_into_id,
        )
    if kind == "strategy":
        return repo_svc.review_strategy_item(
            db,
            item_id,
            action=normalized,
            actor_user_id=actor_user_id,
            note=note,
            merged_into_id=merged_into_id,
        )
    raise ValueError(f"Unknown review kind: {kind}")
