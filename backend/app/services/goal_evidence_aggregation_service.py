"""Aggregate goal and strategy evidence — legacy + v2 scored entries."""

from __future__ import annotations

import json
from collections import Counter
from statistics import mean

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.clinical_evidence import IepGoalCard, SessionGoalEntry, StrategyUseEvent
from app.models.daily_log import DailyLog
from app.models.goal_repository import GoalRepositoryItem, RepositoryItemStatus, StrategyRepositoryItem
from app.models.session import Session as TherapySession
from app.services.clinical_evidence_service import entry_schema_version_from_row
from app.services.clinical_workbench_service import _parse_iep_goals
from app.services import iep_plan_service as iep_svc


def _avg(values: list[int | None]) -> float | None:
    nums = [v for v in values if v is not None]
    if not nums:
        return None
    return round(mean(nums), 2)


def _trend(scores: list[int | None]) -> str | None:
    nums = [v for v in scores if v is not None]
    if len(nums) < 2:
        return None
    recent = nums[-3:]
    prior = nums[-6:-3] if len(nums) >= 6 else nums[:-3]
    if not prior:
        return "insufficient_history"
    if mean(recent) > mean(prior) + 0.25:
        return "improving"
    if mean(recent) < mean(prior) - 0.25:
        return "needs_support"
    return "stable"


def _strength(session_count: int, with_notes: int, strategy_links: int) -> str:
    if session_count >= 4 and with_notes >= 2 and strategy_links >= 1:
        return "strong_operational"
    if session_count >= 2 or with_notes >= 1:
        return "moderate"
    return "weak"


def _json_list(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
        return [str(x) for x in data if x]
    except (TypeError, ValueError, json.JSONDecodeError):
        return []


def _most_common_label(values: list[str | None], limit: int = 1) -> list[str]:
    counts = Counter(v for v in values if v)
    return [label for label, _ in counts.most_common(limit)]


def _load_goals(db: Session, case_id: int) -> list[dict]:
    cards = db.scalars(
        select(IepGoalCard).where(IepGoalCard.case_id == case_id).order_by(IepGoalCard.sort_order)
    ).all()
    if cards:
        return [
            {"id": c.id, "label": c.label, "domain_key": c.domain_key, "source": "iep_goal_cards"}
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
    pending_custom = db.scalar(
        select(func.count())
        .select_from(GoalRepositoryItem)
        .where(
            GoalRepositoryItem.case_id == case_id,
            GoalRepositoryItem.status.in_(
                (RepositoryItemStatus.LOCAL.value, RepositoryItemStatus.CANDIDATE.value)
            ),
        )
    ) or 0

    items = []
    for g in goals:
        label = g.get("label") or ""
        goal_card_id = g.get("id")
        entries: list[SessionGoalEntry] = []
        if log_ids:
            if goal_card_id:
                entries = list(
                    db.scalars(
                        select(SessionGoalEntry).where(
                            SessionGoalEntry.daily_log_id.in_(log_ids),
                            SessionGoalEntry.goal_card_id == goal_card_id,
                        )
                    ).all()
                )
            if not entries:
                entries = [
                    e
                    for e in db.scalars(
                        select(SessionGoalEntry).where(SessionGoalEntry.daily_log_id.in_(log_ids))
                    ).all()
                    if label.lower() in (e.goal_label or "").lower()
                ]

        v2_entries = [e for e in entries if entry_schema_version_from_row(e) == 2]
        legacy_entries = [e for e in entries if entry_schema_version_from_row(e) == 1]
        with_notes = sum(1 for e in entries if (e.response_note or e.measurement_note or "").strip())
        strategy_links = 0
        if entries:
            strategy_links = db.scalar(
                select(func.count())
                .select_from(StrategyUseEvent)
                .where(StrategyUseEvent.daily_log_id.in_([e.daily_log_id for e in entries]))
            ) or 0

        feedback_dist: dict[str, int] = {}
        linked_strategy_events: list[StrategyUseEvent] = []
        if entries:
            linked_strategy_events = list(
                db.scalars(
                    select(StrategyUseEvent).where(
                        StrategyUseEvent.daily_log_id.in_([e.daily_log_id for e in entries])
                    )
                ).all()
            )
            for ev in linked_strategy_events:
                if ev.strategy_feedback:
                    feedback_dist[ev.strategy_feedback] = feedback_dist.get(ev.strategy_feedback, 0) + 1

        environments: set[str] = set()
        for e in entries:
            environments.update(_json_list(e.core_environments_json))
        for ev in linked_strategy_events:
            if ev.environment:
                environments.add(ev.environment)

        items.append(
            {
                "goal_id": goal_card_id,
                "label": label,
                "domain_key": g.get("domain_key"),
                "source": g.get("source"),
                "schema_version": 2 if v2_entries else (1 if legacy_entries else None),
                "session_count": len({e.daily_log_id for e in entries}),
                "sessions_addressed": len({e.daily_log_id for e in entries}),
                "entries_with_notes": with_notes,
                "strategy_links": strategy_links,
                "strategies_used": strategy_links,
                "evidence_strength": _strength(len(entries), with_notes, strategy_links),
                "avg_participation": _avg([e.participation_score for e in v2_entries]),
                "avg_independence": _avg([e.independence_score for e in v2_entries]),
                "avg_goal_achievement": _avg([e.goal_achievement_score for e in v2_entries]),
                "latest_trend": _trend([e.goal_achievement_score for e in sorted(entries, key=lambda x: x.id)]),
                "feedback_distribution": feedback_dist,
                "evidence_count": sum(e.evidence_count or 0 for e in entries),
                "custom_pending_count": pending_custom if len(items) == 0 else 0,
                "legacy_entry_count": len(legacy_entries),
                "support_level_pattern": _most_common_label([e.support_level for e in entries]),
                "environments": sorted(environments),
            }
        )
    if items and pending_custom:
        items[0]["custom_pending_count"] = pending_custom
    return {"case_id": case_id, "goals": items}


def build_strategies_evidence_summary(db: Session, case_id: int) -> dict:
    log_ids = [
        log.id
        for log in db.scalars(
            select(DailyLog).join(TherapySession).where(TherapySession.case_id == case_id)
        ).all()
    ]
    repo = db.scalars(
        select(StrategyRepositoryItem).where(StrategyRepositoryItem.case_id == case_id)
    ).all()
    events: list[StrategyUseEvent] = []
    if log_ids:
        events = list(db.scalars(select(StrategyUseEvent).where(StrategyUseEvent.daily_log_id.in_(log_ids))).all())

    by_label: dict[str, list[StrategyUseEvent]] = {}
    for e in events:
        by_label.setdefault(e.strategy_label, []).append(e)

    items = []
    for label, evs in by_label.items():
        feedback: dict[str, int] = {}
        environments: set[str] = set()
        goal_ids: set[int] = set()
        where_helped = ""
        where_needs_adapting = ""
        strategy_id = None
        for e in sorted(evs, key=lambda x: x.id, reverse=True):
            if e.strategy_feedback:
                feedback[e.strategy_feedback] = feedback.get(e.strategy_feedback, 0) + 1
            if e.environment:
                environments.add(e.environment)
            if e.goal_card_id:
                goal_ids.add(e.goal_card_id)
            if strategy_id is None:
                strategy_id = e.strategy_id or e.custom_strategy_id
            note = (e.outcome_note or e.short_note or "").strip()
            if note and not where_helped and e.strategy_feedback == "HELPFUL":
                where_helped = note
            if note and not where_needs_adapting and e.strategy_feedback in ("NEEDS_ADAPTATION", "CHILD_REJECTED", "NOT_HELPFUL"):
                where_needs_adapting = note
        with_outcome = sum(1 for e in evs if (e.outcome_note or e.short_note or "").strip())
        items.append(
            {
                "strategy_id": strategy_id,
                "label": label,
                "use_count": len(evs),
                "usage_count": len(evs),
                "with_outcome_notes": with_outcome,
                "helpful_count": feedback.get("HELPFUL", 0),
                "partly_helpful_count": feedback.get("PARTLY_HELPFUL", 0),
                "not_helpful_count": feedback.get("NOT_HELPFUL", 0),
                "rejection_count": feedback.get("CHILD_REJECTED", 0) + feedback.get("NEEDS_ADAPTATION", 0),
                "feedback_distribution": feedback,
                "linked_goal_ids": sorted(goal_ids),
                "environments": sorted(environments),
                "evidence_strength": _strength(len(evs), with_outcome, 1 if with_outcome else 0),
                "where_helped": where_helped,
                "where_needs_adapting": where_needs_adapting,
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
                    "usage_count": 0,
                    "with_outcome_notes": 0,
                    "evidence_strength": "weak",
                }
            )
    return {"case_id": case_id, "strategies": items}
