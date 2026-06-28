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
from app.services.clinical_brain_metadata import (
    derive_review_status,
    dump_metadata,
    merge_metadata,
    parse_metadata,
)
from app.services.strategy_repository_stats_service import aggregate_usage_for_strategy


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
    meta = parse_metadata(row.metadata_json)
    scope = row.scope or ("organization" if row.case_id is None else "case")
    return {
        "id": row.id,
        "case_id": row.case_id,
        "domain_key": row.domain_key,
        "label": row.label,
        "rationale": row.rationale,
        "status": row.status,
        "lifecycle_status": row.lifecycle_status,
        "review_status": derive_review_status(
            status=row.status,
            lifecycle_status=row.lifecycle_status,
            review_note=row.review_note,
            scope=scope,
            case_id=row.case_id,
        ),
        "source": row.source,
        "scope": scope,
        "core_domains": _json_list(row.core_domains_json),
        "core_environments": _json_list(row.core_environments_json),
        "baseline_state": row.baseline_state,
        "desired_state": row.desired_state,
        "goal_statement": row.goal_statement,
        "created_by_user_id": row.created_by_user_id,
        "approved_by_user_id": row.approved_by_user_id,
        "approved_at": row.approved_at.isoformat() if row.approved_at else None,
        "source_daily_log_id": row.source_daily_log_id,
        "source_session_id": row.source_session_id,
        "review_note": row.review_note,
        "last_reviewed_at": row.last_reviewed_at.isoformat() if row.last_reviewed_at else None,
        "support_need": meta.get("support_need"),
        "service_type": meta.get("service_type"),
        "age_group": meta.get("age_group"),
        "parent_friendly_explanation": meta.get("parent_friendly_explanation") or row.desired_state,
        "parent_meaning": meta.get("parent_friendly_explanation") or row.desired_state,
        "success_markers": meta.get("success_markers"),
        "evidence_needed": meta.get("evidence_needed"),
        "parent_safe": meta.get("parent_safe", False),
    }


def _strategy_to_dict(row: StrategyRepositoryItem) -> dict:
    steps = _json_list(row.strategy_steps_json)
    meta = parse_metadata(row.metadata_json)
    scope = row.scope or ("organization" if row.case_id is None else "case")
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
        "review_status": derive_review_status(
            status=row.status,
            lifecycle_status=None,
            review_note=row.review_note,
            scope=scope,
            case_id=row.case_id,
        ),
        "source": row.source,
        "scope": scope,
        "core_domains": _json_list(row.core_domains_json),
        "core_environments": _json_list(row.core_environments_json),
        "domain_key": row.domain_key,
        "environment_context": row.environment_context,
        "linked_goal_card_id": row.linked_goal_card_id,
        "created_by_user_id": row.created_by_user_id,
        "approved_by_user_id": row.approved_by_user_id,
        "approved_at": row.approved_at.isoformat() if row.approved_at else None,
        "source_daily_log_id": row.source_daily_log_id,
        "review_note": row.review_note,
        "last_reviewed_at": row.last_reviewed_at.isoformat() if row.last_reviewed_at else None,
        "support_need": meta.get("support_need"),
        "support_level": meta.get("support_level"),
        "service_type": meta.get("service_type"),
        "age_group": meta.get("age_group"),
        "parent_friendly_explanation": meta.get("parent_friendly_explanation"),
        "purpose": row.when_to_use or row.expected_outcome,
        "caution": row.avoid or meta.get("caution"),
        "parent_safe": meta.get("parent_safe", False),
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
    goal_use: str | None = None,
) -> dict:
    status = RepositoryItemStatus.LOCAL.value
    lifecycle = "active"
    source_val = source or "therapist"
    if goal_use == "case_candidate":
        status = RepositoryItemStatus.CANDIDATE.value
        lifecycle = "pending_review"
    elif goal_use == "cm_iep_review":
        status = RepositoryItemStatus.CANDIDATE.value
        lifecycle = "pending_review"
        source_val = "cm_iep_review"
    elif goal_use == "session_log_only":
        status = RepositoryItemStatus.LOCAL.value
        lifecycle = "active"
        source_val = "session_log_only"

    row = GoalRepositoryItem(
        case_id=case_id,
        created_by_user_id=user_id,
        domain_key=domain_key,
        label=label.strip(),
        rationale=rationale,
        status=status,
        source_daily_log_id=source_daily_log_id,
        source_session_id=source_session_id,
        core_domains_json=_dump_json_list(core_domains),
        core_environments_json=_dump_json_list(core_environments),
        baseline_state=baseline_state,
        desired_state=desired_state,
        goal_statement=goal_statement or label.strip(),
        lifecycle_status=lifecycle,
        source=source_val,
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
    strategy_type: str | None = None,
    action: str | None = None,
    metadata: dict | None = None,
) -> dict:
    steps = strategy_steps or []
    how = how_to_use or ("\n".join(steps) if steps else None)
    source_val = strategy_type or source or "therapist"
    status = RepositoryItemStatus.LOCAL.value
    if action == "submit_for_cm_review" or source in ("cm_iep_review", "cm_review"):
        status = RepositoryItemStatus.CANDIDATE.value
        source_val = source or "cm_iep_review"
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
        source=source_val,
        scope="case",
        status=status,
        metadata_json=dump_metadata(metadata),
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


def get_goal_candidate(db: Session, case_id: int, item_id: int) -> GoalRepositoryItem | None:
    row = db.get(GoalRepositoryItem, item_id)
    if not row or row.case_id != case_id:
        return None
    return row


def get_strategy_candidate(db: Session, case_id: int, item_id: int) -> StrategyRepositoryItem | None:
    row = db.get(StrategyRepositoryItem, item_id)
    if not row or row.case_id != case_id:
        return None
    return row


def update_goal_candidate(
    db: Session,
    item_id: int,
    *,
    case_id: int,
    action: str | None = None,
    label: str | None = None,
    goal_statement: str | None = None,
    rationale: str | None = None,
    domain_key: str | None = None,
    metadata: dict | None = None,
) -> dict | None:
    row = get_goal_candidate(db, case_id, item_id)
    if not row:
        return None
    if label:
        row.label = label.strip()
    if goal_statement is not None:
        row.goal_statement = goal_statement
    if rationale is not None:
        row.rationale = rationale
    if domain_key:
        row.domain_key = domain_key
    if metadata:
        row.metadata_json = merge_metadata(row.metadata_json, metadata)
    if action == "submit_for_cm_review":
        row.status = RepositoryItemStatus.CANDIDATE.value
        row.lifecycle_status = "pending_review"
        row.source = row.source or "therapist"
        row.review_note = None
    elif action == "archive":
        row.status = RepositoryItemStatus.ARCHIVED.value
    db.commit()
    db.refresh(row)
    return _goal_to_dict(row)


def update_strategy_candidate(
    db: Session,
    item_id: int,
    *,
    case_id: int,
    action: str | None = None,
    label: str | None = None,
    when_to_use: str | None = None,
    how_to_use: str | None = None,
    avoid: str | None = None,
    domain_key: str | None = None,
    environment_context: str | None = None,
    strategy_steps: list[str] | None = None,
    linked_goal_card_id: int | None = None,
    metadata: dict | None = None,
) -> dict | None:
    row = get_strategy_candidate(db, case_id, item_id)
    if not row:
        return None
    if label:
        row.label = label.strip()
    if when_to_use is not None:
        row.when_to_use = when_to_use
    if how_to_use is not None:
        row.how_to_use = how_to_use
    if avoid is not None:
        row.avoid = avoid
    if domain_key:
        row.domain_key = domain_key
    if environment_context:
        row.environment_context = environment_context
    if strategy_steps is not None:
        row.strategy_steps_json = _dump_json_list(strategy_steps)
    if linked_goal_card_id is not None:
        row.linked_goal_card_id = linked_goal_card_id
    if metadata:
        row.metadata_json = merge_metadata(row.metadata_json, metadata)
    if action == "submit_for_cm_review":
        row.status = RepositoryItemStatus.CANDIDATE.value
        row.review_note = None
    elif action == "archive":
        row.status = RepositoryItemStatus.ARCHIVED.value
    db.commit()
    db.refresh(row)
    return _strategy_to_dict(row)


def _apply_bank_filters(stmt, model, *, q: str = "", domain: str | None = None, status: str | None = None):
    if domain:
        stmt = stmt.where(model.domain_key == domain)
    if status:
        stmt = stmt.where(model.status == status)
    if q.strip():
        stmt = stmt.where(model.label.ilike(f"%{q.strip()}%"))
    return stmt


def list_org_goal_bank(
    db: Session,
    *,
    q: str = "",
    domain: str | None = None,
    status: str | None = None,
    limit: int = 200,
) -> list[dict]:
    stmt = select(GoalRepositoryItem).where(GoalRepositoryItem.case_id.is_(None))
    stmt = _apply_bank_filters(stmt, GoalRepositoryItem, q=q, domain=domain, status=status)
    rows = db.scalars(stmt.order_by(GoalRepositoryItem.id.desc()).limit(limit)).all()
    out = []
    for row in rows:
        d = _goal_to_dict(row)
        d["title"] = row.label
        d["example_wording"] = row.goal_statement or row.label
        d["usage_count"] = 0
        d["related_strategies_count"] = 0
        out.append(d)
    return out


def list_org_strategy_pool(
    db: Session,
    *,
    q: str = "",
    domain: str | None = None,
    status: str | None = None,
    limit: int = 200,
) -> list[dict]:
    stmt = select(StrategyRepositoryItem).where(StrategyRepositoryItem.case_id.is_(None))
    stmt = _apply_bank_filters(stmt, StrategyRepositoryItem, q=q, domain=domain, status=status)
    rows = db.scalars(stmt.order_by(StrategyRepositoryItem.id.desc()).limit(limit)).all()
    out = []
    for row in rows:
        d = _strategy_to_dict(row)
        usage = aggregate_usage_for_strategy(db, row.id)
        d["name"] = row.label
        d["implementation_summary"] = row.how_to_use
        d["environment_tags"] = _json_list(row.core_environments_json) or (
            [row.environment_context] if row.environment_context else []
        )
        d["usage_count"] = usage["usage_count"]
        d["evidence_strength"] = usage["evidence_strength"]
        d["evidence_label"] = usage["evidence_label"]
        d["outcome_pattern"] = None
        out.append(d)
    return out


def create_org_strategy(
    db: Session,
    *,
    user_id: int,
    label: str,
    domain_key: str,
    when_to_use: str | None = None,
    how_to_use: str | None = None,
    avoid: str | None = None,
    strategy_steps: list[str] | None = None,
    metadata: dict | None = None,
    activate: bool = False,
) -> dict:
    status = RepositoryItemStatus.APPROVED.value if activate else RepositoryItemStatus.LOCAL.value
    row = StrategyRepositoryItem(
        case_id=None,
        created_by_user_id=user_id,
        label=label.strip(),
        when_to_use=when_to_use,
        how_to_use=how_to_use or ("\n".join(strategy_steps or []) if strategy_steps else None),
        avoid=avoid,
        domain_key=domain_key,
        strategy_steps_json=_dump_json_list(strategy_steps),
        expected_outcome=when_to_use,
        scope="organization",
        status=status,
        metadata_json=dump_metadata(metadata),
    )
    if activate:
        row.approved_by_user_id = user_id
        row.approved_at = datetime.now(timezone.utc)
    db.add(row)
    db.commit()
    db.refresh(row)
    return _strategy_to_dict(row)


def update_org_strategy(
    db: Session,
    strategy_id: int,
    *,
    user_id: int,
    patch: dict,
) -> dict | None:
    row = db.get(StrategyRepositoryItem, strategy_id)
    if not row or row.case_id is not None:
        return None
    for field in ("label", "when_to_use", "how_to_use", "avoid", "domain_key", "environment_context"):
        if field in patch and patch[field] is not None:
            setattr(row, field, patch[field])
    if patch.get("strategy_steps") is not None:
        row.strategy_steps_json = _dump_json_list(patch["strategy_steps"])
    if patch.get("metadata"):
        row.metadata_json = merge_metadata(row.metadata_json, patch["metadata"])
    if patch.get("status"):
        row.status = patch["status"]
    row.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(row)
    return _strategy_to_dict(row)


def approve_org_strategy(db: Session, strategy_id: int, approver_id: int) -> dict | None:
    row = db.get(StrategyRepositoryItem, strategy_id)
    if not row or row.case_id is not None:
        return None
    row.status = RepositoryItemStatus.APPROVED.value
    row.approved_by_user_id = approver_id
    row.approved_at = datetime.now(timezone.utc)
    row.last_reviewed_at = datetime.now(timezone.utc)
    _record_review(db, item_type="strategy", item_id=strategy_id, action="approve_pool", actor_user_id=approver_id)
    db.commit()
    db.refresh(row)
    return _strategy_to_dict(row)


def deprecate_org_strategy(db: Session, strategy_id: int, actor_id: int, note: str | None = None) -> dict | None:
    row = db.get(StrategyRepositoryItem, strategy_id)
    if not row or row.case_id is not None:
        return None
    row.status = RepositoryItemStatus.ARCHIVED.value
    row.review_note = note
    row.last_reviewed_at = datetime.now(timezone.utc)
    _record_review(db, item_type="strategy", item_id=strategy_id, action="reject", actor_user_id=actor_id, note=note)
    db.commit()
    db.refresh(row)
    return _strategy_to_dict(row)


def merge_org_strategy_stub(
    db: Session, strategy_id: int, canonical_id: int, actor_id: int
) -> dict:
    row = db.get(StrategyRepositoryItem, strategy_id)
    if row:
        row.status = RepositoryItemStatus.ARCHIVED.value
        row.review_note = f"Merged into #{canonical_id}"
        _record_review(
            db,
            item_type="strategy",
            item_id=strategy_id,
            action="merge",
            actor_user_id=actor_id,
            merged_into_id=canonical_id,
        )
        db.commit()
    return {"merge_status": "deferred", "archived_id": strategy_id, "canonical_id": canonical_id}


def search_org_goal_templates(
    db: Session,
    *,
    q: str = "",
    domain: str | None = None,
    limit: int = 50,
) -> list[dict]:
    statuses = (RepositoryItemStatus.APPROVED.value, RepositoryItemStatus.ACTIVE.value)
    stmt = select(GoalRepositoryItem).where(
        GoalRepositoryItem.case_id.is_(None),
        GoalRepositoryItem.status.in_(statuses),
    )
    stmt = _apply_bank_filters(stmt, GoalRepositoryItem, q=q, domain=domain)
    rows = db.scalars(stmt.order_by(GoalRepositoryItem.label).limit(limit)).all()
    return [_goal_to_dict(r) for r in rows]
