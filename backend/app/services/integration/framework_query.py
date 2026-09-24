"""Masked goal and IEP identifier reads. Labels are truncated; narratives stay out."""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.audit import log_audit
from app.core.config import settings
from app.core.pagination import normalize_pagination, paginate_query, paginated_response
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
    page: int = 1,
    page_size: int = 25,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> dict:
    require_scope(principal, "goals:read")
    check_rate_limit(principal.client_id, limit_per_minute=principal.client.rate_limit_per_minute)
    page, page_size = normalize_pagination(page, page_size, settings.integration_max_page_size)
    allowed = granted_case_ids(db, principal)
    if not allowed:
        empty = paginated_response([], 0, page, page_size)
        return {"goals": empty, "strategies": empty}
    goal_rows, goal_total = paginate_query(
        db,
        select(GoalRepositoryItem)
        .where(GoalRepositoryItem.case_id.in_(allowed))
        .order_by(GoalRepositoryItem.id.desc()),
        page=page,
        page_size=page_size,
        max_page_size=settings.integration_max_page_size,
    )
    strategy_rows, strategy_total = paginate_query(
        db,
        select(StrategyRepositoryItem)
        .where(StrategyRepositoryItem.case_id.in_(allowed))
        .order_by(StrategyRepositoryItem.id.desc()),
        page=page,
        page_size=page_size,
        max_page_size=settings.integration_max_page_size,
    )
    payload = {
        "goals": paginated_response(
            [
                {
                    "goal_id": row.id,
                    "case_id": row.case_id,
                    "domain_key": row.domain_key,
                    "status": row.status,
                    "label": _excerpt(row.label),
                }
                for row in goal_rows
            ],
            goal_total,
            page,
            page_size,
        ),
        "strategies": paginated_response(
            [
                {
                    "strategy_id": row.id,
                    "case_id": row.case_id,
                    "linked_goal_card_id": row.linked_goal_card_id,
                    "status": row.status,
                    "environment_context": row.environment_context,
                    "label": _excerpt(row.label),
                }
                for row in strategy_rows
            ],
            strategy_total,
            page,
            page_size,
        ),
    }
    log_audit(
        db,
        actor_user_id=None,
        integration_client_id=principal.client_id,
        action="integration.goals_list",
        entity_type="goal",
        entity_id=None,
        new_value={
            "goals": len(payload["goals"]["items"]),
            "strategies": len(payload["strategies"]["items"]),
            "page": page,
        },
        ip_address=ip_address,
        user_agent=user_agent,
    )
    return payload


def list_iep_framework(
    db: Session,
    principal: IntegrationPrincipal,
    *,
    page: int = 1,
    page_size: int = 25,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> dict:
    require_scope(principal, "iep:read")
    check_rate_limit(principal.client_id, limit_per_minute=principal.client.rate_limit_per_minute)
    page, page_size = normalize_pagination(page, page_size, settings.integration_max_page_size)
    allowed = granted_case_ids(db, principal)
    if not allowed:
        return {"plans": paginated_response([], 0, page, page_size)}
    plans, plan_total = paginate_query(
        db,
        select(IepPlan).where(IepPlan.case_id.in_(allowed)).order_by(IepPlan.id.desc()),
        page=page,
        page_size=page_size,
        max_page_size=settings.integration_max_page_size,
    )
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
        "plans": paginated_response(
            [
                {
                    "iep_id": plan.id,
                    "case_id": plan.case_id,
                    "version": plan.version,
                    "status": plan.status,
                    "goal_count": goal_counts.get(plan.id, 0),
                    "strategy_count": strategy_counts.get(plan.id, 0),
                }
                for plan in plans
            ],
            plan_total,
            page,
            page_size,
        )
    }
    log_audit(
        db,
        actor_user_id=None,
        integration_client_id=principal.client_id,
        action="integration.iep_list",
        entity_type="iep_plan",
        entity_id=None,
        new_value={"plans": len(payload["plans"]["items"]), "page": page},
        ip_address=ip_address,
        user_agent=user_agent,
    )
    return payload
