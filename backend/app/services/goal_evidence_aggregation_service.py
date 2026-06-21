"""Aggregate goal and strategy evidence with operational strength labels."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.clinical_evidence import GoalEvidenceEvent, IepGoalCard, SessionGoalEntry, StrategyUseEvent
from app.models.daily_log import DailyLog
from app.models.goal_repository import StrategyRepositoryItem
from app.models.iep_plan import IepPlan
from app.models.session import Session as TherapySession
from app.services.clinical_workbench_service import _parse_iep_goals
from app.services import iep_plan_service as iep_svc


def _strength(session_count: int, with_notes: int, strategy_links: int) -> str:
    if session_count >= 4 and with_notes >= 2 and strategy_links >= 1:
        return "strong_operational"
    if session_count >= 2 or with_notes >= 1:
        return "moderate"
    return "weak"


def _load_goals(db: Session, case_id: int) -> list[dict]:
    cards = db.scalars(
        select(IepGoalCard).where(IepGoalCard.case_id == case_id).order_by(IepGoalCard.sort_order)
    ).all()
    if cards:
        return [
            {"id": c.id, "label": c.label, "domain_key": None, "source": "iep_goal_cards"}
            for c in cards
        ]
    plan = iep_svc.get_latest_plan(db, case_id)
    return _parse_iep_goals(plan)


def build_goals_evidence_summary(db: Session, case_id: int) -> dict:
    goals = _load_goals(db, case_id)
    log_ids = [
        log.id
        for log in db.scalars(
            select(DailyLog)
            .join(TherapySession)
            .where(TherapySession.case_id == case_id)
            .options(selectinload(DailyLog.session))
        ).all()
    ]
    items = []
    for g in goals:
        label = g.get("label") or ""
        entries = []
        if log_ids:
            entries = db.scalars(
                select(SessionGoalEntry).where(
                    SessionGoalEntry.daily_log_id.in_(log_ids),
                    SessionGoalEntry.goal_label.contains(label[:60]) if len(label) > 60 else SessionGoalEntry.goal_label == label,
                )
            ).all()
            if not entries:
                entries = [
                    e
                    for e in db.scalars(
                        select(SessionGoalEntry).where(SessionGoalEntry.daily_log_id.in_(log_ids))
                    ).all()
                    if label.lower() in (e.goal_label or "").lower()
                ]
        with_notes = sum(1 for e in entries if (e.response_note or "").strip())
        strategy_links = 0
        if entries:
            strategy_links = db.scalar(
                select(func.count())
                .select_from(StrategyUseEvent)
                .where(StrategyUseEvent.daily_log_id.in_([e.daily_log_id for e in entries]))
            ) or 0
        ev_events = db.scalar(
            select(func.count())
            .select_from(GoalEvidenceEvent)
            .where(GoalEvidenceEvent.case_id == case_id)
        ) or 0
        items.append(
            {
                "goal_id": g.get("id"),
                "label": label,
                "domain_key": g.get("domain_key"),
                "source": g.get("source"),
                "session_count": len({e.daily_log_id for e in entries}),
                "entries_with_notes": with_notes,
                "strategy_links": strategy_links,
                "evidence_strength": _strength(len(entries), with_notes, strategy_links),
                "evidence_events": ev_events if len(items) == 0 else 0,
            }
        )
    return {"case_id": case_id, "goals": items}


def build_strategies_evidence_summary(db: Session, case_id: int) -> dict:
    log_ids = [
        log.id
        for log in db.scalars(
            select(DailyLog)
            .join(TherapySession)
            .where(TherapySession.case_id == case_id)
        ).all()
    ]
    repo = db.scalars(
        select(StrategyRepositoryItem).where(StrategyRepositoryItem.case_id == case_id)
    ).all()
    events = []
    if log_ids:
        events = db.scalars(
            select(StrategyUseEvent).where(StrategyUseEvent.daily_log_id.in_(log_ids))
        ).all()
    by_label: dict[str, list[StrategyUseEvent]] = {}
    for e in events:
        by_label.setdefault(e.strategy_label, []).append(e)
    items = []
    for label, evs in by_label.items():
        with_outcome = sum(1 for e in evs if (e.outcome_note or "").strip())
        items.append(
            {
                "label": label,
                "use_count": len(evs),
                "with_outcome_notes": with_outcome,
                "evidence_strength": _strength(len(evs), with_outcome, 1 if with_outcome else 0),
            }
        )
    for s in repo:
        if not any(i["label"] == s.label for i in items):
            items.append(
                {
                    "strategy_id": s.id,
                    "label": s.label,
                    "status": s.status,
                    "use_count": 0,
                    "with_outcome_notes": 0,
                    "evidence_strength": "weak",
                }
            )
    return {"case_id": case_id, "strategies": items}
