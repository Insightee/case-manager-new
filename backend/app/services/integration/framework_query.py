"""Masked goal and IEP identifier reads. Labels are truncated; narratives stay out."""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.audit import log_audit
from app.core.config import settings
from app.models.goal_repository import GoalRepositoryItem, StrategyRepositoryItem
from app.models.iep_identity import IepGoalItem, IepStrategyItem
from app.models.iep_plan import IepPlan
from app.services.integration.access import IntegrationPrincipal, granted_case_ids, require_scope
from app.services.integration.rate_limit import check_rate_limit

_EXCERPT = 80


def _excerpt(value: str | None) -> str:
    raw = " ".join((value or "").split())
    if len(raw) <= _EXCERPT:
        return raw
    return raw[: _EXCERPT - 1] + "…"


def list_goal_framework(
    db: Session,
    principal: IntegrationPrincipal,
    *,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> dict:
    require_scope(principal, "goals:read")
    check_rate_limit(principal.client_id, limit_per_minute=principal.client.rate_limit_per_minute)
    allowed = granted_case_ids(db, principal)
    cap = settings.integration_max_page_size
    if not allowed:
        return {"goals": [], "strategies": []}
    goals = db.scalars(
        select(GoalRepositoryItem)
        .where(GoalRepositoryItem.case_id.in_(allowed))
        .order_by(GoalRepositoryItem.id.desc())
        .limit(cap)
    ).all()
    strategies = db.scalars(
        select(StrategyRepositoryItem)
        .where(StrategyRepositoryItem.case_id.in_(allowed))
        .order_by(StrategyRepositoryItem.id.desc())
        .limit(cap)
    ).all()
    payload = {
        "goals": [
            {
                "goal_id": row.id,
                "case_id": row.case_id,
                "domain_key": row.domain_key,
                "status": row.status,
                "label": _excerpt(row.label),
            }
            for row in goals
        ],
        "strategies": [
            {
                "strategy_id": row.id,
                "case_id": row.case_id,
                "goal_id": row.linked_goal_card_id,
                "status": row.status,
                "environment_context": row.environment_context,
                "label": _excerpt(row.label),
            }
            for row in strategies
        ],
    }
    log_audit(
        db,
        actor_user_id=None,
        integration_client_id=principal.client_id,
        action="integration.goals_list",
        entity_type="goal",
        entity_id=None,
        new_value={"goals": len(payload["goals"]), "strategies": len(payload["strategies"])},
        ip_address=ip_address,
        user_agent=user_agent,
    )
    return payload


def list_iep_framework(
    db: Session,
    principal: IntegrationPrincipal,
    *,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> dict:
    require_scope(principal, "iep:read")
    check_rate_limit(principal.client_id, limit_per_minute=principal.client.rate_limit_per_minute)
    allowed = granted_case_ids(db, principal)
    if not allowed:
        return {"plans": []}
    plans = db.scalars(
        select(IepPlan).where(IepPlan.case_id.in_(allowed)).order_by(IepPlan.id.desc()).limit(settings.integration_max_page_size)
    ).all()
    plan_ids = [plan.id for plan in plans]
    goal_counts: dict[int, int] = {}
    strategy_counts: dict[int, int] = {}
    if plan_ids:
        for plan_id, count in db.execute(
            select(IepGoalItem.iep_plan_id, func.count())
            .where(IepGoalItem.iep_plan_id.in_(plan_ids), IepGoalItem.retired_at.is_(None))
            .group_by(IepGoalItem.iep_plan_id)
        ).all():
            goal_counts[int(plan_id)] = int(count)
        for plan_id, count in db.execute(
            select(IepStrategyItem.iep_plan_id, func.count())
            .where(IepStrategyItem.iep_plan_id.in_(plan_ids), IepStrategyItem.retired_at.is_(None))
            .group_by(IepStrategyItem.iep_plan_id)
        ).all():
            strategy_counts[int(plan_id)] = int(count)
    payload = {
        "plans": [
            {
                "iep_id": plan.id,
                "case_id": plan.case_id,
                "version": plan.version,
                "status": plan.status,
                "goal_count": goal_counts.get(plan.id, 0),
                "strategy_count": strategy_counts.get(plan.id, 0),
            }
            for plan in plans
        ]
    }
    log_audit(
        db,
        actor_user_id=None,
        integration_client_id=principal.client_id,
        action="integration.iep_list",
        entity_type="iep_plan",
        entity_id=None,
        new_value={"plans": len(payload["plans"])},
        ip_address=ip_address,
        user_agent=user_agent,
    )
    return payload
