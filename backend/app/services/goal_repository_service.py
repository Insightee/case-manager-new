from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.goal_repository import (
    GoalRepositoryItem,
    RepositoryItemStatus,
    RepositoryReviewEvent,
    StrategyRepositoryItem,
)


def _json_list(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
        return [str(x) for x in data if x]
    except (TypeError, ValueError, json.JSONDecodeError):
        return []


def _dump_json_list(items: list[str] | None) -> str | None:
    if not items:
        return None
    cleaned = [str(x).strip() for x in items if str(x).strip()]
    return json.dumps(cleaned) if cleaned else None


def _goal_to_dict(row: GoalRepositoryItem) -> dict:
    return {
        "id": row.id,
        "case_id": row.case_id,
        "domain_key": row.domain_key,
        "label": row.label,
        "rationale": row.rationale,
        "status": row.status,
        "lifecycle_status": row.lifecycle_status,
        "source": row.source,
        "scope": row.scope,
        "core_domains": _json_list(row.core_domains_json),
        "core_environments": _json_list(row.core_environments_json),
        "baseline_state": row.baseline_state,
        "desired_state": row.desired_state,
        "goal_statement": row.goal_statement,
        "created_by_user_id": row.created_by_user_id,
        "source_daily_log_id": row.source_daily_log_id,
        "source_session_id": row.source_session_id,
        "review_note": row.review_note,
    }


def _strategy_to_dict(row: StrategyRepositoryItem) -> dict:
    steps = _json_list(row.strategy_steps_json)
    return {
        "id": row.id,
        "case_id": row.case_id,
        "label": row.label,
        "when_to_use": row.when_to_use,
        "how_to_use": row.how_to_use,
        "strategy_steps": steps,
        "expected_outcome": row.expected_outcome,
        "avoid": row.avoid,
        "status": row.status,
        "source": row.source,
        "scope": row.scope,
        "core_domains": _json_list(row.core_domains_json),
        "core_environments": _json_list(row.core_environments_json),
        "domain_key": row.domain_key,
        "environment_context": row.environment_context,
        "linked_goal_card_id": row.linked_goal_card_id,
        "created_by_user_id": row.created_by_user_id,
        "source_daily_log_id": row.source_daily_log_id,
        "review_note": row.review_note,
    }


def _record_review(
    db: Session,
    *,
    item_type: str,
    item_id: int,
    action: str,
    actor_user_id: int,
    note: str | None = None,
    merged_into_id: int | None = None,
) -> None:
    db.add(
        RepositoryReviewEvent(
            item_type=item_type,
            item_id=item_id,
            action=action,
            actor_user_id=actor_user_id,
            note=note,
            merged_into_id=merged_into_id,
        )
    )


def list_goal_candidates(db: Session, case_id: int) -> list[dict]:
    rows = db.scalars(
        select(GoalRepositoryItem)
        .where(GoalRepositoryItem.case_id == case_id)
        .order_by(GoalRepositoryItem.id.desc())
    ).all()
    return [_goal_to_dict(r) for r in rows]


def list_pending_for_case(db: Session, case_id: int) -> dict:
    pending_statuses = (RepositoryItemStatus.LOCAL.value, RepositoryItemStatus.CANDIDATE.value)
    goals = db.scalars(
        select(GoalRepositoryItem).where(
            GoalRepositoryItem.case_id == case_id,
            GoalRepositoryItem.status.in_(pending_statuses),
        )
    ).all()
    strategies = db.scalars(
        select(StrategyRepositoryItem).where(
            StrategyRepositoryItem.case_id == case_id,
            StrategyRepositoryItem.status.in_(pending_statuses),
        )
    ).all()
    return {"goals": [_goal_to_dict(g) for g in goals], "strategies": [_strategy_to_dict(s) for s in strategies]}


def create_goal_candidate(
    db: Session,
    *,
    case_id: int,
    user_id: int,
    domain_key: str,
    label: str,
    rationale: str | None = None,
    source_daily_log_id: int | None = None,
    source_session_id: int | None = None,
    core_domains: list[str] | None = None,
    core_environments: list[str] | None = None,
    baseline_state: str | None = None,
    desired_state: str | None = None,
    goal_statement: str | None = None,
    source: str | None = "therapist",
) -> dict:
    row = GoalRepositoryItem(
        case_id=case_id,
        created_by_user_id=user_id,
        domain_key=domain_key,
        label=label.strip(),
        rationale=rationale,
        status=RepositoryItemStatus.LOCAL.value,
        source_daily_log_id=source_daily_log_id,
        source_session_id=source_session_id,
        core_domains_json=_dump_json_list(core_domains),
        core_environments_json=_dump_json_list(core_environments),
        baseline_state=baseline_state,
        desired_state=desired_state,
        goal_statement=goal_statement or label.strip(),
        lifecycle_status="active",
        source=source,
        scope="case",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _goal_to_dict(row)


def create_strategy_candidate(
    db: Session,
    *,
    case_id: int,
    user_id: int,
    label: str,
    when_to_use: str | None = None,
    how_to_use: str | None = None,
    avoid: str | None = None,
    domain_key: str | None = None,
    environment_context: str | None = None,
    linked_goal_card_id: int | None = None,
    source_daily_log_id: int | None = None,
    core_domains: list[str] | None = None,
    core_environments: list[str] | None = None,
    strategy_steps: list[str] | None = None,
    expected_outcome: str | None = None,
    source: str | None = "therapist",
) -> dict:
    steps = strategy_steps or []
    how = how_to_use or ("\n".join(steps) if steps else None)
    row = StrategyRepositoryItem(
        case_id=case_id,
        created_by_user_id=user_id,
        label=label.strip(),
        when_to_use=when_to_use or expected_outcome,
        how_to_use=how,
        avoid=avoid,
        domain_key=domain_key,
        environment_context=environment_context,
        linked_goal_card_id=linked_goal_card_id,
        source_daily_log_id=source_daily_log_id,
        core_domains_json=_dump_json_list(core_domains),
        core_environments_json=_dump_json_list(core_environments),
        strategy_steps_json=_dump_json_list(steps),
        expected_outcome=expected_outcome or when_to_use,
        source=source,
        scope="case",
        status=RepositoryItemStatus.LOCAL.value,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _strategy_to_dict(row)


def approve_goal_candidate(db: Session, item_id: int, approver_id: int) -> dict | None:
    row = db.get(GoalRepositoryItem, item_id)
    if not row:
        return None
    row.status = RepositoryItemStatus.APPROVED.value
    row.approved_by_user_id = approver_id
    row.approved_at = datetime.now(timezone.utc)
    if row.case_id is not None:
        row.case_id = None
    _record_review(db, item_type="goal", item_id=item_id, action="approve_pool", actor_user_id=approver_id)
    db.commit()
    db.refresh(row)
    return _goal_to_dict(row)


def review_goal_item(
    db: Session,
    item_id: int,
    *,
    action: str,
    actor_user_id: int,
    note: str | None = None,
    merged_into_id: int | None = None,
) -> dict | None:
    row = db.get(GoalRepositoryItem, item_id)
    if not row:
        return None
    if action == "approve_case":
        row.status = RepositoryItemStatus.ACTIVE.value
    elif action == "approve_pool":
        row.status = RepositoryItemStatus.APPROVED.value
        row.case_id = None
    elif action == "request_edits":
        row.status = RepositoryItemStatus.CANDIDATE.value
        row.review_note = note
    elif action == "reject":
        row.status = RepositoryItemStatus.ARCHIVED.value
        row.review_note = note
    elif action == "merge" and merged_into_id:
        row.status = RepositoryItemStatus.ARCHIVED.value
        row.review_note = note or f"Merged into #{merged_into_id}"
    else:
        raise ValueError(f"Unknown review action: {action}")
    row.approved_by_user_id = actor_user_id
    row.approved_at = datetime.now(timezone.utc)
    _record_review(
        db,
        item_type="goal",
        item_id=item_id,
        action=action,
        actor_user_id=actor_user_id,
        note=note,
        merged_into_id=merged_into_id,
    )
    db.commit()
    db.refresh(row)
    return _goal_to_dict(row)


def review_strategy_item(
    db: Session,
    item_id: int,
    *,
    action: str,
    actor_user_id: int,
    note: str | None = None,
    merged_into_id: int | None = None,
) -> dict | None:
    row = db.get(StrategyRepositoryItem, item_id)
    if not row:
        return None
    if action == "approve_case":
        row.status = RepositoryItemStatus.ACTIVE.value
    elif action == "approve_pool":
        row.status = RepositoryItemStatus.APPROVED.value
        row.case_id = None
    elif action == "request_edits":
        row.status = RepositoryItemStatus.CANDIDATE.value
        row.review_note = note
    elif action == "reject":
        row.status = RepositoryItemStatus.ARCHIVED.value
        row.review_note = note
    elif action == "merge" and merged_into_id:
        row.status = RepositoryItemStatus.ARCHIVED.value
        row.review_note = note or f"Merged into #{merged_into_id}"
    else:
        raise ValueError(f"Unknown review action: {action}")
    row.approved_by_user_id = actor_user_id
    row.approved_at = datetime.now(timezone.utc)
    _record_review(
        db,
        item_type="strategy",
        item_id=item_id,
        action=action,
        actor_user_id=actor_user_id,
        note=note,
        merged_into_id=merged_into_id,
    )
    db.commit()
    db.refresh(row)
    return _strategy_to_dict(row)


def list_strategy_candidates(db: Session, case_id: int) -> list[dict]:
    rows = db.scalars(
        select(StrategyRepositoryItem)
        .where(StrategyRepositoryItem.case_id == case_id)
        .order_by(StrategyRepositoryItem.id.desc())
    ).all()
    return [_strategy_to_dict(r) for r in rows]
