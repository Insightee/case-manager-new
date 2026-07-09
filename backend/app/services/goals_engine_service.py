"""Goals & Strategy Engine — single payload for case workspace + admin repository."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.case import Case
from app.models.clinical_evidence import IepGoalCard
from app.models.goal_repository import GoalRepositoryItem, RepositoryItemStatus, StrategyRepositoryItem
from app.models.user import User
from app.services import goal_evidence_aggregation_service as ev_agg

IEP_ASSIGNED_STATUSES = ("active", "paused")
ASSIGNED_REPO_STATUSES = (
    RepositoryItemStatus.ACTIVE.value,
    RepositoryItemStatus.APPROVED.value,
)
EXCLUDED_LIFECYCLES = frozenset({"archived", "achieved", "closed", "revised"})


def _json_list(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
        return [str(x) for x in data if x]
    except (TypeError, ValueError, json.JSONDecodeError):
        return []


def _json_steps(raw: str | None) -> list[str]:
    return _json_list(raw)


def _dump_json_list(items: list[str] | None) -> str | None:
    if not items:
        return None
    cleaned = [str(x).strip() for x in items if str(x).strip()]
    return json.dumps(cleaned) if cleaned else None


def _user_name(db: Session, user_id: int | None) -> str | None:
    if not user_id:
        return None
    user = db.get(User, user_id)
    if not user:
        return None
    return user.full_name or user.email


def _goal_row_dict(db: Session, row: GoalRepositoryItem) -> dict[str, Any]:
    return {
        "id": row.id,
        "case_id": row.case_id,
        "domain_key": row.domain_key,
        "label": row.label,
        "rationale": row.rationale,
        "status": row.status,
        "lifecycle_status": row.lifecycle_status or "active",
        "source": row.source or "therapist",
        "scope": row.scope or ("organization" if row.case_id is None else "case"),
        "core_domains": _json_list(row.core_domains_json),
        "core_environments": _json_list(row.core_environments_json),
        "baseline_state": row.baseline_state,
        "desired_state": row.desired_state,
        "goal_statement": row.goal_statement or row.label,
        "created_by_user_id": row.created_by_user_id,
        "created_by_name": _user_name(db, row.created_by_user_id),
        "source_daily_log_id": row.source_daily_log_id,
        "source_session_id": row.source_session_id,
        "review_note": row.review_note,
        "is_pending": row.status in (
            RepositoryItemStatus.LOCAL.value,
            RepositoryItemStatus.CANDIDATE.value,
        ),
    }


def _strategy_row_dict(db: Session, row: StrategyRepositoryItem) -> dict[str, Any]:
    steps = _json_steps(row.strategy_steps_json)
    if not steps and row.how_to_use:
        steps = [s.strip() for s in row.how_to_use.split("\n") if s.strip()][:3]
    return {
        "id": row.id,
        "case_id": row.case_id,
        "label": row.label,
        "when_to_use": row.when_to_use,
        "how_to_use": row.how_to_use,
        "strategy_steps": steps,
        "expected_outcome": row.expected_outcome or row.when_to_use,
        "avoid": row.avoid,
        "status": row.status,
        "source": row.source or "therapist",
        "scope": row.scope or ("organization" if row.case_id is None else "case"),
        "core_domains": _json_list(row.core_domains_json),
        "core_environments": _json_list(row.core_environments_json),
        "domain_key": row.domain_key,
        "environment_context": row.environment_context,
        "linked_goal_card_id": row.linked_goal_card_id,
        "created_by_user_id": row.created_by_user_id,
        "created_by_name": _user_name(db, row.created_by_user_id),
        "source_daily_log_id": row.source_daily_log_id,
        "review_note": row.review_note,
        "is_pending": row.status in (
            RepositoryItemStatus.LOCAL.value,
            RepositoryItemStatus.CANDIDATE.value,
        ),
    }


def _iep_goal_dict(card: IepGoalCard) -> dict[str, Any]:
    return {
        "goal_card_id": card.id,
        "label": card.label,
        "goal_brief": card.baseline or card.why_it_matters or "",
        "goal_statement": card.goal_statement or card.label,
        "domain_key": card.domain_key,
        "status": card.status,
        "source": "iep",
        "scope": "case",
        "lifecycle_status": "paused" if card.status == "paused" else "active",
    }


def _is_assigned_case_goal(row: GoalRepositoryItem) -> bool:
    if row.case_id is None:
        return False
    if row.status in (RepositoryItemStatus.LOCAL.value, RepositoryItemStatus.CANDIDATE.value):
        return False
    if row.status == RepositoryItemStatus.ARCHIVED.value:
        return False
    life = (row.lifecycle_status or "active").lower()
    if life in EXCLUDED_LIFECYCLES:
        return False
    if life in ("active", "paused"):
        return True
    return row.status in ASSIGNED_REPO_STATUSES


def _is_assigned_case_strategy(row: StrategyRepositoryItem) -> bool:
    if row.case_id is None:
        return False
    if row.status in (
        RepositoryItemStatus.LOCAL.value,
        RepositoryItemStatus.CANDIDATE.value,
        RepositoryItemStatus.ARCHIVED.value,
    ):
        return False
    return row.status in ASSIGNED_REPO_STATUSES


def _goal_evidence_index(summary: dict[str, Any]) -> dict[int, dict[str, Any]]:
    out: dict[int, dict[str, Any]] = {}
    for item in summary.get("goals") or []:
        gid = item.get("goal_id")
        if gid is not None:
            out[int(gid)] = item
    return out


def _strategy_evidence_index(summary: dict[str, Any]) -> tuple[dict[int, dict[str, Any]], dict[str, dict[str, Any]]]:
    by_id: dict[int, dict[str, Any]] = {}
    by_label: dict[str, dict[str, Any]] = {}
    for item in summary.get("strategies") or []:
        sid = item.get("strategy_id")
        if sid is not None:
            by_id[int(sid)] = item
        label = (item.get("label") or "").strip().lower()
        if label:
            by_label[label] = item
    return by_id, by_label


def _merge_goal_evidence(goal: dict[str, Any], ev: dict[str, Any] | None) -> dict[str, Any]:
    if not ev:
        goal.setdefault("evidence_count", 0)
        goal.setdefault("session_count", 0)
        return goal
    goal["evidence_count"] = ev.get("evidence_count") or ev.get("session_count") or 0
    goal["session_count"] = ev.get("session_count") or ev.get("sessions_addressed") or 0
    goal["strategy_links"] = ev.get("strategy_links") or 0
    goal["evidence_strength"] = ev.get("evidence_strength")
    goal["latest_trend"] = ev.get("latest_trend")
    return goal


def _merge_strategy_evidence(
    strategy: dict[str, Any],
    ev: dict[str, Any] | None,
) -> dict[str, Any]:
    if not ev:
        strategy.setdefault("evidence_count", 0)
        strategy.setdefault("usage_count", 0)
        return strategy
    strategy["evidence_count"] = ev.get("usage_count") or ev.get("use_count") or 0
    strategy["usage_count"] = ev.get("usage_count") or ev.get("use_count") or 0
    strategy["helpful_count"] = ev.get("helpful_count") or 0
    strategy["evidence_strength"] = ev.get("evidence_strength")
    strategy["where_helped"] = ev.get("where_helped")
    strategy["where_needs_adapting"] = ev.get("where_needs_adapting")
    return strategy


def build_goals_engine_payload(db: Session, case_id: int) -> dict[str, Any]:
    """Single payload for GoalStrategyEnginePage."""
    case = db.get(Case, case_id)
    iep_cards = db.scalars(
        select(IepGoalCard)
        .where(IepGoalCard.case_id == case_id, IepGoalCard.status.in_(IEP_ASSIGNED_STATUSES))
        .order_by(IepGoalCard.sort_order, IepGoalCard.id)
    ).all()

    repo_goals = db.scalars(
        select(GoalRepositoryItem)
        .where(
            or_(GoalRepositoryItem.case_id == case_id, GoalRepositoryItem.case_id.is_(None)),
            GoalRepositoryItem.status.notin_([RepositoryItemStatus.ARCHIVED.value]),
        )
        .order_by(GoalRepositoryItem.id.desc())
    ).all()

    repo_strategies = db.scalars(
        select(StrategyRepositoryItem)
        .where(
            or_(StrategyRepositoryItem.case_id == case_id, StrategyRepositoryItem.case_id.is_(None)),
            StrategyRepositoryItem.status.notin_([RepositoryItemStatus.ARCHIVED.value]),
        )
        .order_by(StrategyRepositoryItem.id.desc())
    ).all()

    pending_goals = [g for g in repo_goals if g.status in (RepositoryItemStatus.LOCAL.value, RepositoryItemStatus.CANDIDATE.value)]
    pending_strategies = [
        s for s in repo_strategies if s.status in (RepositoryItemStatus.LOCAL.value, RepositoryItemStatus.CANDIDATE.value)
    ]

    domains = sorted({c.domain_key for c in iep_cards if c.domain_key})
    for g in repo_goals:
        domains.extend(_json_list(g.core_domains_json))
        if g.domain_key:
            domains.append(g.domain_key)
    domains = sorted(set(domains))

    goals_evidence = ev_agg.build_goals_evidence_summary(db, case_id)
    strategies_evidence = ev_agg.build_strategies_evidence_summary(db, case_id)
    goal_ev_idx = _goal_evidence_index(goals_evidence)
    strat_ev_by_id, strat_ev_by_label = _strategy_evidence_index(strategies_evidence)

    case_goals = [g for g in repo_goals if g.case_id == case_id]
    case_strategies = [s for s in repo_strategies if s.case_id == case_id]
    assigned_goals = [g for g in case_goals if _is_assigned_case_goal(g)]
    assigned_strategies = [s for s in case_strategies if _is_assigned_case_strategy(s)]

    iep_goal_rows = [
        _merge_goal_evidence(_iep_goal_dict(c), goal_ev_idx.get(c.id))
        for c in iep_cards
    ]
    assigned_repo_goal_rows = [
        _merge_goal_evidence(_goal_row_dict(db, g), goal_ev_idx.get(g.id))
        for g in assigned_goals
    ]
    assigned_strategy_rows = []
    for s in assigned_strategies:
        row = _strategy_row_dict(db, s)
        ev = strat_ev_by_id.get(s.id) or strat_ev_by_label.get((s.label or "").strip().lower())
        assigned_strategy_rows.append(_merge_strategy_evidence(row, ev))

    return {
        "case_id": case_id,
        "child_name": case.child.full_name if case and case.child else None,
        "iep_goals": iep_goal_rows,
        "assigned_goals": iep_goal_rows + assigned_repo_goal_rows,
        "goals": [_goal_row_dict(db, g) for g in case_goals],
        "org_pool_goals": [_goal_row_dict(db, g) for g in repo_goals if g.case_id is None],
        "assigned_strategies": assigned_strategy_rows,
        "strategies": [_strategy_row_dict(db, s) for s in case_strategies],
        "org_pool_strategies": [_strategy_row_dict(db, s) for s in repo_strategies if s.case_id is None],
        "pending_count": len(pending_goals) + len(pending_strategies),
        "pending_goals": len(pending_goals),
        "pending_strategies": len(pending_strategies),
        "filter_domains": domains,
    }


def list_admin_goal_strategy_repository(db: Session, *, limit: int = 100) -> dict[str, Any]:
    """Cross-case pending queue + org pool for CM/admin."""
    pending_statuses = (RepositoryItemStatus.LOCAL.value, RepositoryItemStatus.CANDIDATE.value)

    pending_goals = db.scalars(
        select(GoalRepositoryItem)
        .where(GoalRepositoryItem.status.in_(pending_statuses))
        .order_by(GoalRepositoryItem.id.desc())
        .limit(limit)
    ).all()

    pending_strategies = db.scalars(
        select(StrategyRepositoryItem)
        .where(StrategyRepositoryItem.status.in_(pending_statuses))
        .order_by(StrategyRepositoryItem.id.desc())
        .limit(limit)
    ).all()

    org_goals = db.scalars(
        select(GoalRepositoryItem)
        .where(
            GoalRepositoryItem.case_id.is_(None),
            GoalRepositoryItem.status.in_(
                (RepositoryItemStatus.APPROVED.value, RepositoryItemStatus.ACTIVE.value)
            ),
        )
        .order_by(GoalRepositoryItem.id.desc())
        .limit(limit)
    ).all()

    org_strategies = db.scalars(
        select(StrategyRepositoryItem)
        .where(
            StrategyRepositoryItem.case_id.is_(None),
            StrategyRepositoryItem.status.in_(
                (RepositoryItemStatus.APPROVED.value, RepositoryItemStatus.ACTIVE.value)
            ),
        )
        .order_by(StrategyRepositoryItem.id.desc())
        .limit(limit)
    ).all()

    def _with_case(row: GoalRepositoryItem | StrategyRepositoryItem) -> dict[str, Any]:
        base = _goal_row_dict(db, row) if isinstance(row, GoalRepositoryItem) else _strategy_row_dict(db, row)
        if row.case_id:
            case = db.get(Case, row.case_id)
            base["case_code"] = case.case_code if case else None
            base["child_name"] = case.child.full_name if case and case.child else None
        return base

    return {
        "pending_goals": [_with_case(g) for g in pending_goals],
        "pending_strategies": [_with_case(s) for s in pending_strategies],
        "org_pool_goals": [_goal_row_dict(db, g) for g in org_goals],
        "org_pool_strategies": [_strategy_row_dict(db, s) for s in org_strategies],
    }


__all__ = ["build_goals_engine_payload", "list_admin_goal_strategy_repository", "_dump_json_list"]
