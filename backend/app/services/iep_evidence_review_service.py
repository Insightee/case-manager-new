"""Deterministic IEP evidence review suggestions — no LLM."""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import date, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.clinical_evidence import IepGoalCard
from app.models.clinical_review_queue import ClinicalReviewQueueItem
from app.models.iep_plan import IepPlan
from app.models.iep_review_suggestion import IepReviewSuggestion, IepReviewSuggestionStatus
from app.services import clinical_evidence_event_service as cee_svc
from app.services.clinical_review_queue_service import _record_event

_DEBUG_LOG = "/Users/midhunnoble/insighte case maanger /case-manager-new-1/.cursor/debug-3264f0.log"


def _agent_log(location: str, message: str, data: dict, hypothesis_id: str) -> None:
    # #region agent log
    try:
        import json
        import time

        with open(_DEBUG_LOG, "a", encoding="utf-8") as fh:
            fh.write(
                json.dumps(
                    {
                        "sessionId": "3264f0",
                        "location": location,
                        "message": message,
                        "data": data,
                        "hypothesisId": hypothesis_id,
                        "timestamp": int(time.time() * 1000),
                    }
                )
                + "\n"
            )
    except OSError:
        pass
    # #endregion


def _find_draft_suggestion(
    db: Session,
    *,
    case_id: int,
    goal_card_id: int | None,
    suggestion_type: str,
) -> IepReviewSuggestion | None:
    return db.scalars(
        select(IepReviewSuggestion).where(
            IepReviewSuggestion.case_id == case_id,
            IepReviewSuggestion.goal_card_id == goal_card_id,
            IepReviewSuggestion.suggestion_type == suggestion_type,
            IepReviewSuggestion.status == IepReviewSuggestionStatus.DRAFT.value,
        )
    ).first()


def _month_key(d: date) -> str:
    return d.strftime("%Y-%m")


def build_iep_evidence_review(
    db: Session,
    *,
    case_id: int,
    iep_plan_id: int | None = None,
    period_from: date | None = None,
    period_to: date | None = None,
) -> dict[str, Any]:
    period_to = period_to or date.today()
    period_from = period_from or (period_to - timedelta(days=30))

    plan = None
    if iep_plan_id:
        plan = db.get(IepPlan, iep_plan_id)
    if not plan:
        plan = db.scalars(
            select(IepPlan).where(IepPlan.case_id == case_id).order_by(IepPlan.id.desc())
        ).first()

    months = {_month_key(period_from)}
    if _month_key(period_to) != _month_key(period_from):
        months.add(_month_key(period_to))

    events: list[dict] = []
    for m in months:
        events.extend(cee_svc.materialize_for_case_month(db, case_id, m))

    cards = (
        db.scalars(select(IepGoalCard).where(IepGoalCard.iep_plan_id == plan.id)).all()
        if plan
        else db.scalars(select(IepGoalCard).where(IepGoalCard.case_id == case_id)).all()
    )

    goal_evidence = []
    for card in cards:
        label = card.label or card.goal_statement or ""
        matched = [e for e in events if (e.get("goal_linkage", {}).get("goal_title") or "").lower() == label.lower()]
        envs = sorted({e.get("context", {}).get("environment") for e in matched if e.get("context", {}).get("environment")})
        strategies: dict[str, dict] = defaultdict(lambda: {"use_count": 0, "adapted_count": 0})
        for e in matched:
            sl = e.get("strategy_linkage", {}) or {}
            name = sl.get("strategy_title")
            if not name:
                continue
            strategies[name]["strategy_name"] = name
            strategies[name]["strategy_id"] = sl.get("strategy_id")
            strategies[name]["use_count"] += 1
            if sl.get("adaptation_type"):
                strategies[name]["adapted_count"] += 1

        suggestions = []
        if len(matched) < 3:
            suggestions.append(
                {
                    "type": "needs_more_evidence",
                    "reason": "Goal has limited session evidence in this review period.",
                    "severity": "normal",
                    "source_ids": [e.get("identity", {}).get("evidence_event_id") for e in matched[:5]],
                }
            )
        if matched and not any(e.get("support_and_response", {}).get("child_response") for e in matched):
            suggestions.append(
                {
                    "type": "improve_documentation",
                    "reason": "Sessions note this goal but child response is not consistently recorded.",
                    "severity": "normal",
                    "source_ids": [],
                }
            )
        if len(envs) == 1:
            suggestions.append(
                {
                    "type": "consider_generalisation_environment",
                    "reason": f"Evidence is mostly from {envs[0]}; consider whether support is needed elsewhere.",
                    "severity": "normal",
                    "source_ids": [],
                }
            )
        adapted_total = sum(s["adapted_count"] for s in strategies.values())
        if adapted_total >= 3:
            suggestions.append(
                {
                    "type": "review_strategy_adaptation",
                    "reason": "Strategies for this goal were adapted several times — worth reviewing what fits.",
                    "severity": "normal",
                    "source_ids": [],
                }
            )

        persisted = []
        for s in suggestions:
            existing = _find_draft_suggestion(
                db,
                case_id=case_id,
                goal_card_id=card.id,
                suggestion_type=s["type"],
            )
            if existing:
                existing.reason = s["reason"]
                existing.supporting_evidence_json = json.dumps(s.get("source_ids") or [])
                existing.confidence = s.get("severity")
                s["suggestion_id"] = existing.id
                persisted.append(s)
                _agent_log(
                    "iep_evidence_review_service.py:build",
                    "reused draft suggestion",
                    {"suggestion_id": existing.id, "type": s["type"], "goal_card_id": card.id},
                    "H1",
                )
                continue
            row = IepReviewSuggestion(
                case_id=case_id,
                iep_plan_id=plan.id if plan else None,
                goal_card_id=card.id,
                suggestion_type=s["type"],
                reason=s["reason"],
                supporting_evidence_json=json.dumps(s.get("source_ids") or []),
                confidence=s.get("severity"),
                status=IepReviewSuggestionStatus.DRAFT.value,
            )
            db.add(row)
            db.flush()
            s["suggestion_id"] = row.id
            persisted.append(s)
            _agent_log(
                "iep_evidence_review_service.py:build",
                "created draft suggestion",
                {"suggestion_id": row.id, "type": s["type"], "goal_card_id": card.id},
                "H1",
            )

        goal_evidence.append(
            {
                "goal_id": card.id,
                "goal_title": label,
                "sessions_addressed": len({e.get("identity", {}).get("daily_log_id") for e in matched}),
                "evidence_events": len(matched),
                "environments": envs,
                "strategies": list(strategies.values()),
                "parent_inputs_count": 0,
                "monthly_report_refs": [],
                "quality_flags": [],
                "review_suggestions": persisted,
            }
        )

    if plan:
        db.commit()

    return {
        "iep_id": plan.id if plan else None,
        "review_period": {"from": period_from.isoformat(), "to": period_to.isoformat()},
        "goal_evidence": goal_evidence,
    }


def send_suggestion_to_review(db: Session, suggestion_id: int, actor_user_id: int) -> dict[str, Any]:
    sug = db.get(IepReviewSuggestion, suggestion_id)
    if not sug:
        raise ValueError("Suggestion not found")
    existing = db.scalars(
        select(ClinicalReviewQueueItem).where(
            ClinicalReviewQueueItem.item_type == "iep_review_suggestion",
            ClinicalReviewQueueItem.source_entity_kind == "iep_review_suggestion",
            ClinicalReviewQueueItem.source_entity_id == sug.id,
            ClinicalReviewQueueItem.status.in_(("pending", "in_review", "revision_requested")),
        )
    ).first()
    if existing:
        _agent_log(
            "iep_evidence_review_service.py:send_to_review",
            "reused queue item",
            {"queue_item_id": existing.id, "suggestion_id": sug.id},
            "H2",
        )
        return {"queue_item_id": existing.id, "suggestion_id": sug.id}
    item = ClinicalReviewQueueItem(
        item_type="iep_review_suggestion",
        status="pending",
        source_case_id=sug.case_id,
        source_goal_id=sug.goal_card_id,
        source_entity_kind="iep_review_suggestion",
        source_entity_id=sug.id,
        title=f"IEP review: {sug.suggestion_type.replace('_', ' ')}",
        summary=sug.reason,
    )
    db.add(item)
    db.flush()
    _record_event(
        db,
        item=item,
        actor_user_id=actor_user_id,
        old_status=None,
        new_status="pending",
        action="create",
        note="From IEP evidence review suggestion",
    )
    sug.status = IepReviewSuggestionStatus.DRAFT.value
    db.commit()
    _agent_log(
        "iep_evidence_review_service.py:send_to_review",
        "created queue item",
        {"queue_item_id": item.id, "suggestion_id": sug.id},
        "H2",
    )
    return {"queue_item_id": item.id, "suggestion_id": sug.id}
